import os
import sys
import logging
import json
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import CensusState
from src.tools.chart_tool import ChartTool
from src.tools.table_tool import TableTool

logger = logging.getLogger(__name__)


def get_chart_params(census_data: Dict[str, Any], chart_type: str) -> Dict[str, str]:
    """
    Dynamically determine chart parameters based on census data structure.

    Args:
        census_data: Data from state.artifacts.census_data with format:
                    {"data": [["headers"], ["rows"]], "variables": {...}}
        chart_type: "bar" or "line"

    Returns:
        Dict with x_column, y_column, title keys
    """
    try:
        # Extract data array from census_data
        if (
            "data" in census_data
            and isinstance(census_data["data"], list)
            and len(census_data["data"]) >= 2
        ):
            headers = census_data["data"][0]  # First row is headers
            data_rows = census_data["data"][1:]  # Remaining rows are data
        else:
            raise ValueError("Invalid census_data format")

        # Find NAME/LOCATION column (x-axis for both chart types)
        name_column = None
        for header in headers:
            if header.upper() in ["NAME", "LOCATION"]:
                name_column = header
                break

        # For time series data, use Year as x-axis
        if chart_type == "line":
            year_column = None
            for header in headers:
                if header.upper() in ["YEAR", "YEAR_END"]:
                    year_column = header
                    break

            if year_column:
                # Year is x-axis for time series
                name_column = year_column

        # Final fallback: use first column if still no name_column found
        if not name_column:
            name_column = headers[0] if headers else "Location"

        # Find numeric columns (y-axis candidates)
        numeric_columns = []
        for header in headers:
            # Exclude geography and time columns from y-axis
            excluded_headers = [
                "NAME",
                "LOCATION",
                "GEO_ID",
                "STATE",
                "COUNTY",
                "YEAR",
                "YEAR_END",
            ]
            if header.upper() not in excluded_headers:
                # Check if this column has numeric data
                try:
                    # Test first few rows to see if they're numeric
                    if data_rows:
                        for row in data_rows[:3]:  # Check first 3 rows
                            if len(row) > headers.index(header):
                                value = row[headers.index(header)]
                                if (
                                    value
                                    and str(value)
                                    .replace(",", "")
                                    .replace("-", "")
                                    .isdigit()
                                ):
                                    numeric_columns.append(header)
                                    break
                except (IndexError, ValueError):
                    continue

        # Select y_column based on chart type and available data
        y_column = None

        if chart_type == "line":
            # For line charts, prioritize Census variable columns (usually longer codes)
            for col in numeric_columns:
                if len(col) > 8 and col.startswith(
                    ("B", "C", "S", "DP")
                ):  # Census variable patterns
                    y_column = col
                    break

        # Fallback for line charts or default for bar charts
        if not y_column:
            # Use first numeric column
            y_column = (
                numeric_columns[0]
                if numeric_columns
                else headers[1]
                if len(headers) > 1
                else headers[0]
            )

        # Generate appropriate title
        title = f"Census Data by {name_column}"
        if chart_type == "bar":
            title = f"Comparison of {y_column} by {name_column}"
        elif chart_type == "line":
            title = f"{y_column} Trends by {name_column}"

        # Enhance title with variable description if available
        if "variables" in census_data and y_column in census_data["variables"]:
            var_desc = census_data["variables"][y_column]
            title = f"{var_desc} by {name_column}"

        return {"x_column": name_column, "y_column": y_column, "title": title}

    except Exception as e:
        logger.error(f"Error determining chart parameters: {e}")
        # Fallback to safe defaults
        return {
            "x_column": "NAME",
            "y_column": headers[1] if len(headers) > 1 else headers[0],
            "title": f"Census Data Visualization ({chart_type})",
        }


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
                result = chart_tool._run(
                    json.dumps(
                        {
                            "chart_type": chart_spec.get("type", "bar"),
                            "x_column": chart_params["x_column"],
                            "y_column": chart_params["y_column"],
                            "title": chart_params["title"],
                            "data": census_data,
                        }
                    )
                )

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
