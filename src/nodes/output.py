import os
import sys
import logging
import json
import pandas as pd
from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import CensusState
from src.tools.chart_tool import ChartTool
from src.tools.table_tool import TableTool

logger = logging.getLogger(__name__)


def format_chart_title(
    y_column: str, x_column: str, chart_type: str, variables: Dict[str, str] = None
) -> str:
    """
    Format chart title with human-readable variable name and code.

    Args:
        y_column: Variable code (e.g., "B01003_001E")
        x_column: X-axis column name (e.g., "NAME")
        chart_type: "bar" or "line"
        variables: Optional dict mapping variable codes to labels
                   e.g., {"B01003_001E": "Total Population"}

    Returns:
        Formatted title like "Total Population (B01003_001E) by NAME"
        or "B01003_001E by NAME" if no label available

    Examples:
        >>> format_chart_title("B01003_001E", "NAME", "bar", {"B01003_001E": "Total Population"})
        'Total Population (B01003_001E) by NAME'
        >>> format_chart_title("B01003_001E", "NAME", "bar", None)
        'B01003_001E by NAME'
        >>> format_chart_title("S2701_C01_001E", "NAME", "line", {"S2701_C01_001E": "Health Insurance Coverage"})
        'Health Insurance Coverage (S2701_C01_001E) Trend'
    """
    # Get human-readable label if available
    y_label = None
    if variables and y_column in variables:
        y_label = variables[y_column].strip()
        # Validate: empty string after strip means invalid label
        if not y_label:
            logger.warning(
                f"Variable '{y_column}' has empty label in variables dict - using code-only title"
            )
            y_label = None

    # Format y-axis part: use label with code in parentheses, or just code
    if y_label:
        y_display = f"{y_label} ({y_column})"
    else:
        y_display = y_column

    # Format title based on chart type
    if chart_type == "bar":
        title = f"{y_display} by {x_column}"
    elif chart_type == "line":
        title = f"{y_display} Trend"
    else:
        title = f"{y_display} - Census Data Visualization"

    return title


def _detect_geography_column(
    df: pd.DataFrame, headers: list, x_column: str = None
) -> Optional[str]:
    """
    Detect geography column with priority order (less granular first).

    Priority: state > county > place > NAME > other geography columns

    Args:
        df: DataFrame with data
        headers: List of column headers
        x_column: Optional x-axis column to exclude from consideration

    Returns:
        Column name if found, None otherwise.
    """
    # Geography column priority order (less granular first)
    geography_priority = [
        "state",
        "county",
        "place",
        "NAME",  # Full geographic name
        "geo_id",
        "GEO_ID",
    ]

    # Check priority order (exclude x_column)
    for geo_col in geography_priority:
        if geo_col in headers and geo_col != x_column:
            return geo_col

    # Check for columns containing geography keywords (lower priority)
    for header in headers:
        if header == x_column:
            continue  # Skip x_column
        header_lower = header.lower()
        if any(
            keyword in header_lower
            for keyword in ["state", "county", "place", "name", "geo", "area", "region"]
        ):
            return header

    return None


def get_chart_params(census_data: Dict[str, Any], chart_type: str) -> Dict[str, str]:
    """
    Dynamically determine chart parameters from actual data structure.
    Adapts to ANY column names the agent provides.
    Auto-detects multi-series when geography + time columns exist.
    """
    try:
        # Extract headers from data
        if (
            "data" in census_data
            and isinstance(census_data["data"], list)
            and len(census_data["data"]) >= 2
        ):
            headers = census_data["data"][0]
        else:
            raise ValueError("Invalid census_data format")

        if len(headers) < 2:
            raise ValueError("Need at least 2 columns for chart")

        # Create DataFrame temporarily to detect geography columns
        df_temp = pd.DataFrame(census_data["data"][1:], columns=headers)

        # Identify column types by content inspection
        text_columns = []
        numeric_columns = []
        time_columns = []

        # Sample first data row to determine types
        sample_row = census_data["data"][1] if len(census_data["data"]) > 1 else []

        for i, header in enumerate(headers):
            if i >= len(sample_row):
                continue

            value = str(sample_row[i]).replace(",", "")
            header_upper = header.upper()

            # Check for time columns
            if any(
                keyword in header_upper
                for keyword in ["YEAR", "DATE", "TIME", "PERIOD"]
            ):
                time_columns.append(header)
            # Check if numeric
            elif value.replace(".", "").replace("-", "").isdigit():
                numeric_columns.append(header)
            # Otherwise text
            else:
                text_columns.append(header)

        # Determine x_column (categorical or time axis)
        x_column = None
        if chart_type == "line" and time_columns:
            # Time series: use time column for x-axis
            x_column = time_columns[0]
        elif text_columns:
            # Use first text column for categorical x-axis
            x_column = text_columns[0]
        else:
            # Fallback: use first column
            x_column = headers[0]

        # Determine y_column (numeric data)
        y_column = None
        if numeric_columns:
            # Use first numeric column that isn't the x_column
            for col in numeric_columns:
                if col != x_column:
                    y_column = col
                    break
            # If all numeric columns are x_column, use first numeric anyway
            if not y_column:
                y_column = numeric_columns[0]
        else:
            # Fallback: use second column if available
            y_column = headers[1] if len(headers) > 1 else headers[0]

        # Auto-detect multi-series: check for geography column + multiple unique values
        color_column = None
        geography_column = _detect_geography_column(df_temp, headers, x_column)

        if geography_column:
            # Check if multiple unique values exist (indicates multi-series)
            unique_geos = df_temp[geography_column].nunique()
            if unique_geos > 1:
                # Multi-series detected: use geography column for color grouping
                color_column = geography_column
                logger.info(
                    f"Multi-series detected: {unique_geos} unique values in '{geography_column}' column"
                )
            else:
                logger.info(
                    f"Single geography detected: only 1 unique value in '{geography_column}' - no color grouping"
                )

        # Generate title
        if chart_type in ["bar", "line"]:
            # Extract variables mapping if available
            variables = census_data.get("variables", {})

            # Log if variables dict is missing (helps debug title formatting)
            if not variables:
                logger.info(
                    f"No variables dict provided in census_data - using code-only title for '{y_column}'"
                )

            # For multi-series: exclude geography from title (legend will show it)
            # For single-series: include x_column in title as before
            if color_column:
                # Multi-series: title should be "Variable by X" (geography in legend)
                title = format_chart_title(y_column, x_column, chart_type, variables)
            else:
                # Single-series: original behavior
                title = format_chart_title(y_column, x_column, chart_type, variables)
        else:
            title = "Census Data Visualization"

        result = {"x_column": x_column, "y_column": y_column, "title": title}
        if color_column:
            result["color_column"] = color_column

        return result

    except Exception as e:
        logger.error(f"Error determining chart parameters: {e}")
        # SAFE fallback: use first two columns from actual data
        if "data" in census_data and len(census_data.get("data", [])) > 0:
            headers = census_data["data"][0]
            return {
                "x_column": headers[0] if headers else "Column1",
                "y_column": headers[1] if len(headers) > 1 else "Column2",
                "title": f"Census Data Visualization ({chart_type})",
            }
        # Ultimate fallback
        return {"x_column": "Location", "y_column": "Value", "title": "Chart"}


def output_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Generate charts and tables from census data
    """

    final_result = state.final or {}
    charts_needed = final_result.get("charts_needed", [])
    tables_needed = final_result.get("tables_needed", [])
    census_data = state.artifacts.get("census_data", {})

    generated_files = []

    # Create charts if needed
    if charts_needed and census_data:
        chart_tool = ChartTool()
        for chart_spec in charts_needed:
            try:
                # Determine parameters
                chart_params = get_chart_params(
                    census_data, chart_spec.get("type", "bar")
                )

                logger.info("=== output_node Chart Generation ===")
                logger.info(f"Chart type: {chart_spec.get('type', 'bar')}")
                logger.info(
                    f"Chart params: x={chart_params['x_column']}, y={chart_params['y_column']}"
                )
                logger.info(f"Census data keys: {list(census_data.keys())}")

                # Log data structure details
                if "data" in census_data:
                    if isinstance(census_data["data"], list):
                        logger.info(
                            f"Data is list with {len(census_data['data'])} elements"
                        )
                        if len(census_data["data"]) > 0:
                            logger.info(f"Data headers: {census_data['data'][0]}")
                            if len(census_data["data"]) > 1:
                                logger.info(f"First data row: {census_data['data'][1]}")
                    elif isinstance(census_data["data"], dict):
                        logger.info(
                            f"Data is dict with keys: {list(census_data['data'].keys())}"
                        )

                # Validate column names exist in data
                if (
                    "data" in census_data
                    and isinstance(census_data["data"], list)
                    and len(census_data["data"]) > 0
                ):
                    headers = census_data["data"][0]
                    logger.info("Checking if selected columns exist in headers...")
                    logger.info(
                        f"  x_column '{chart_params['x_column']}' in headers: {chart_params['x_column'] in headers}"
                    )
                    logger.info(
                        f"  y_column '{chart_params['y_column']}' in headers: {chart_params['y_column'] in headers}"
                    )

                logger.info("=== Calling ChartTool ===\n")

                # Call the tool with proper JSON format
                chart_input = {
                    "chart_type": chart_spec.get("type", "bar"),
                    "x_column": chart_params["x_column"],
                    "y_column": chart_params["y_column"],
                    "title": chart_params["title"],
                    "data": census_data,
                }
                # Add color_column if multi-series was detected
                if "color_column" in chart_params:
                    chart_input["color_column"] = chart_params["color_column"]

                result = chart_tool._run(json.dumps(chart_input))

                generated_files.append(result)
            except Exception as e:
                logger.error(f"Failed to create chart: {e}")

    # Create tables if needed
    if tables_needed and census_data:  # Note: 'if', not 'elif'
        table_tool = TableTool()
        for table_spec in tables_needed:
            try:
                result = table_tool._run(
                    json.dumps(
                        {
                            "format": table_spec.get("format", "csv"),
                            "filename": table_spec.get("filename"),
                            "title": table_spec.get("title", "Census Data"),
                            "data": census_data,
                        }
                    )
                )

                generated_files.append(result)
            except Exception as e:
                logger.error(f"Failed to create table: {e}")

    # Get existing final from state (preserve answer_text, charts_needed, etc.)
    existing_final = state.final or {}

    # Merge generated_files into existing final
    merged_final = {
        **existing_final,
        "generated_files": generated_files,
    }

    return {
        "final": merged_final,
        "logs": [f"output: generated {len(generated_files)} files"],
    }
