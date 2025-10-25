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

        # Find NAME column (x-axis for both chart types)
        name_column = None
        for header in headers:
            if header.upper() in ["NAME", "LOCATION"]:
                name_column = header
                break

        if not name_column:
            # Fallback: use first column if no NAME found
            name_column = headers[0] if headers else "Location"

        # Find numeric columns (y-axis candidates)
        numeric_columns = []
        for header in headers:
            if header.upper() not in ["NAME", "LOCATION", "GEO_ID", "STATE", "COUNTY"]:
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
            # For line charts, prioritize time series data
            # Look for year columns or time-related columns first
            for col in numeric_columns:
                if any(
                    year_indicator in col.upper()
                    for year_indicator in ["YEAR", "TIME", "DATE"]
                ):
                    y_column = col
                    break

            # If no time column, look for Census variable columns (usually longer codes)
            if not y_column:
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

    return {
        "final": {"generated_files": generated_files},
        "logs": [f"output: generated {len(generated_files)} files"],
    }
