import logging
import pandas as pd
from typing import Dict, Any, Literal
from langchain_core.runnables import RunnableConfig


from src.domain.census_tool_contract import StrictCensusApiRawTable
from src.domain.rendered_output_contract import RenderedArtifact
from src.domain.variable_metada_contract import VariableLabels
from src.services.census_render_adapter import response_to_tabular_payload
from src.state.types import CensusState, FinalResponseState
from src.tools.chart_tool import ChartTool, ChartToolInput
from src.tools.table_tool import TableTool, TableToolInput

logger = logging.getLogger(__name__)


def format_chart_title(
    y_column: str,
    x_column: str,
    chart_type: str,
    variables: dict[str, str] | None = None,
    multi_series: bool = False,
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
        if multi_series:
            # Multi-series line chart: "Variable by Year" format
            title = f"{y_display} by {x_column}"
        else:
            # Single-series line chart: "Variable Trend" format
            title = f"{y_display} Trend"
    else:
        title = f"{y_display} - Census Data Visualization"

    return title


def _detect_geography_column(
    df: pd.DataFrame, headers: list, x_column: str | None = None
) -> str | None:
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


def _classify_columns(
    headers: list[str], sample_row: list[Any]
) -> tuple[list[str], list[str], list[str]]:
    """
    Classify columns into text, numeric, and time columns.
    """

    text_columns: list[str] = []
    numeric_columns: list[str] = []
    time_columns: list[str] = []

    for i, header in enumerate(headers):
        if i >= len(sample_row):
            continue

        value = str(sample_row[i]).replace(",", "")
        header_upper = header.upper()

        # Check for time columns
        if any(
            keyword in header_upper for keyword in ["YEAR", "DATE", "TIME", "PERIOD"]
        ):
            time_columns.append(header)

        # Check if numeric
        elif value.replace(".", "").replace("-", "").isdigit():
            numeric_columns.append(header)

        # Otherwise text
        else:
            text_columns.append(header)

    return text_columns, numeric_columns, time_columns


def _pick_x_column(
    chart_type: Literal["bar", "line"],
    headers: list[str],
    text_columns: list[str],
    time_columns: list[str],
) -> str:
    """
    Pick the x-axis column from typed raw-table metadata.
    """

    if chart_type == "line" and time_columns:
        return time_columns[0]

    if text_columns:
        # Use first text column for categorical x-axis
        return text_columns[0]

    # Fallback: use first column
    return headers[0]


def _pick_y_column(
    numeric_columns: list[str],
    headers: list[str],
    x_column: str,
) -> str:
    """
    Pick the y_column based on the numeric columns and the x_column.
    """

    if numeric_columns:
        y_column: str | None = None
        # Use first numeric column that isn't the x_column
        for col in numeric_columns:
            if col != x_column:
                y_column = col
                break
        # If all numeric columns are x_column, use first numeric anyway
        if y_column is None:
            return numeric_columns[0]
        return y_column

    # Fallback: use second column if available
    return headers[1] if len(headers) > 1 else headers[0]


def _pick_color_column(
    df: pd.DataFrame, headers: list[str], x_column: str
) -> str | None:
    geography_column = _detect_geography_column(df, headers, x_column)
    if not geography_column:
        return None

    unique_geos = df[geography_column].nunique()
    if unique_geos > 1:
        logger.info(
            "Multi-series detected: %s unique values in '%s' column",
            unique_geos,
            geography_column,
        )
        return geography_column

    logger.info(
        "Single geography detected: only 1 unique value in '%s' - no color grouping",
        geography_column,
    )
    return None


def _get_variable_map(variable_labels: VariableLabels | None) -> dict[str, str] | None:
    return variable_labels.labels if variable_labels is not None else None


def _build_chart_title(
    y_column: str,
    x_column: str,
    chart_type: Literal["bar", "line"],
    variables: dict[str, str] | None,
    color_column: str | None,
) -> str:
    if not variables:
        logger.info(
            "No variables dict provided in census_data - using code-only title for '%s'",
            y_column,
        )

    return format_chart_title(
        y_column,
        x_column,
        chart_type,
        variables,
        multi_series=color_column is not None,
    )


def get_chart_params(
    raw_data: StrictCensusApiRawTable,
    chart_type: Literal["bar", "line"],
    variable_labels: VariableLabels | None = None,
) -> Dict[str, str]:
    """
    Dynamically determine chart parameters from actual data structure.
    Adapts to ANY column names the agent provides.
    Auto-detects multi-series when geography + time columns exist.
    """
    try:
        headers = raw_data.headers
        rows = raw_data.rows

        if len(headers) < 2:
            raise ValueError("Need at least 2 columns for chart")

        # Create DataFrame temporarily to detect geography columns
        df_temp = pd.DataFrame(rows, columns=pd.Index(headers))

        # Sample first data row to determine types
        sample_row = rows[0] if len(rows) > 0 else []

        text_columns, numeric_columns, time_columns = _classify_columns(
            headers, sample_row
        )

        x_column = _pick_x_column(chart_type, headers, text_columns, time_columns)
        y_column = _pick_y_column(numeric_columns, headers, x_column)
        color_column = _pick_color_column(df_temp, headers, x_column)
        variables = _get_variable_map(variable_labels)
        title = _build_chart_title(
            y_column=y_column,
            x_column=x_column,
            chart_type=chart_type,
            variables=variables,
            color_column=color_column,
        )

        result = {"x_column": x_column, "y_column": y_column, "title": title}
        if color_column:
            result["color_column"] = color_column

        return result

    except Exception as e:
        logger.error(f"Error determining chart parameters: {e}")

        # Ultimate fallback
        return {"x_column": "Location", "y_column": "Value", "title": "Chart"}


def output_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Generate charts and tables from census data
    """

    final_result = state.final or FinalResponseState()
    charts_needed = final_result.charts_needed
    tables_needed = final_result.tables_needed
    census_data = state.artifacts.census_data if state.artifacts else None
    generated_files: list[RenderedArtifact] = list(final_result.generated_files)
    raw_table = (
        response_to_tabular_payload(census_data)
        if census_data is not None and census_data.success and census_data.row_count > 0
        else None
    )

    # Create charts if needed
    if charts_needed and raw_table is not None:
        chart_tool = ChartTool()
        for chart_spec in charts_needed:
            try:
                # Determine parameters
                chart_params = get_chart_params(
                    raw_table,
                    chart_spec.type,
                    state.artifacts.variable_labels if state.artifacts else None,
                )

                logger.info("=== output_node Chart Generation ===")
                logger.info(f"Chart type: {chart_spec.type}")
                logger.info(
                    f"Chart params: x={chart_params['x_column']}, y={chart_params['y_column']}"
                )

                logger.info("=== Calling ChartTool ===\n")

                # Call the tool with typed input format
                chart_input = ChartToolInput(
                    chart_type=chart_spec.type,
                    x_column=chart_params["x_column"],
                    y_column=chart_params["y_column"],
                    title=chart_spec.title or chart_params["title"],
                    color_column=chart_params.get("color_column"),
                    data=raw_table,
                )
                # Add color_column if multi-series was detected
                chart_output = chart_tool.render(chart_input)
                generated_files.append(
                    RenderedArtifact(
                        kind="chart",
                        path=chart_output.path,
                        mime_type=chart_output.mime_type,
                        title=chart_output.spec.title,
                    )
                )

            except Exception as e:
                logger.error(f"Failed to create chart: {e}")

    # Create tables if needed
    if tables_needed and raw_table is not None:
        table_tool = TableTool()
        for table_spec in tables_needed:
            try:
                table_input = TableToolInput(
                    format=table_spec.format,
                    filename=table_spec.filename,
                    title=table_spec.title or "Census Data",
                    data=raw_table,
                )
                table_output = table_tool.render(table_input)

                generated_files.append(
                    RenderedArtifact(
                        kind="table",
                        path=table_output.path,
                        mime_type=table_output.mime_type,
                        title=table_output.spec.title,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to create table: {e}")

    # Get existing final from state (preserve answer_text, charts_needed, etc.)
    return {
        "final": final_result.model_copy(update={"generated_files": generated_files}),
        "logs": [f"output: generated {len(generated_files)} files"],
    }
