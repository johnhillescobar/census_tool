import logging
import pandas as pd
from pathlib import Path
from typing import Any, Literal
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from src.domain.census_tool_contract import StrictCensusApiRawTable
from src.domain.final_output_contract import FinalChartSpec
from src.domain.rendered_output_contract import ChartOutput
from src.services.census_render_adapter import response_to_dataframe
from src.tools.json_parse import parse_first_json

logger = logging.getLogger(__name__)


# TODO: remove this function and replace it with a function that uses the StrictCensusApiRawTable model. See T2-CG-010.
def _coerce_legacy_table_data(value: Any) -> Any:
    """Accept legacy table payloads during the typed-tool migration."""
    if isinstance(value, StrictCensusApiRawTable):
        return value

    if not isinstance(value, dict):
        return value

    data_rows = value.get("data")
    if isinstance(data_rows, list) and len(data_rows) >= 2:
        return {"headers": data_rows[0], "rows": data_rows[1:]}

    nested = value.get("data")
    if isinstance(nested, dict):
        nested_rows = nested.get("data")
        if isinstance(nested_rows, list) and len(nested_rows) >= 2:
            return {"headers": nested_rows[0], "rows": nested_rows[1:]}

    return value


class ChartToolInput(BaseModel):
    """Input for chart creation"""

    model_config = ConfigDict(extra="forbid")

    chart_type: Literal["bar", "line"] = Field(
        ..., description="Chart type: 'bar' for comparisons, 'line' for trends"
    )
    x_column: str = Field(..., description="Column name for x-axis")
    y_column: str = Field(..., description="Column name for y-axis")
    title: str = Field(default="Census Data Visualization", description="Chart title")
    color_column: str | None = Field(
        default=None, description="Column name for color grouping"
    )
    data: StrictCensusApiRawTable = Field(
        ..., description="Census data dict from census_api_call tool"
    )


class ChartTool(BaseTool):
    """Create data visualizations (bar, line charts)"""

    name: str = "create_chart"
    description: str = """
    Create data visualizations from census data
    
    Supports both single-series and multi-series charts (auto-detected).
    Multi-series charts automatically group by geography when multiple areas are present.
    
    Input must be valid JSON with these fields:
    - chart_type: Chart type (bar, line)
    - x_column: Column name for x-axis
    - y_column: Column name for y-axis  
    - title: Chart title (optional, defaults to 'Census Data Visualization')
    - color_column: Optional column name for multi-series grouping (auto-detected if not provided)
    - data: Census data dict from census_api_call tool
    """

    # args_schema = ChartToolInput  # Disabled for ReAct compatibility
    model_config = ConfigDict(extra="forbid")

    # --- FUTURE PHASE (PHASE 3): real sync + async coexistence ---
    #
    # Current state:
    # - `render()` is synchronous and is invoked from `src/workflows/output.py` to build typed
    #   ChartOutput paths + MIME for `generated_files`; it is irrelevant to LangChain tool plumbing.
    # - `_run`/`_execute` are synchronous for the agent string response path.
    # - `_arun` forwards to `_run`, so whenever an async orchestrator invokes the async hook, blocking
    #   code still executes on the event loop (no cooperative yield).
    #
    # Blocking hotspots: pandas/DataFrame paths, Plotly Figure construction + Kaleido/png export via
    # `Figure.write_image`, disk writes, HTML fallback in `_write_chart` / duplicated save block in `render`.
    #
    # When implementing this phase:
    # 1) Factor a single private sync primitive (e.g. `_produce_chart_output(...) -> ChartOutput` or tuple)
    #    used by both `render()` and `_execute()`, so `_write_chart`/`render` never diverge.
    # 2) `_arun` should typically `await asyncio.to_thread(sync_impl, ...)`, `run_in_executor`, or isolate
    #    heavyweight export only—measure before splitting; Kaleido dominates cost.
    # 3) If `output.py`/`output_node` ever becomes async, either `await asyncio.to_thread(tool.render...)`
    #    against the same sync primitive or expose an explicit async workflow API layered on thread offload.
    # 4) Document thread-safety: Plotly/matplotlib backends are historically not concurrency-safe unless
    #    each invocation is isolated—verify before parallelizing `_arun` calls.
    # --- END FUTURE PHASE ---

    # TODO: remove str and dict input types and replace with ChartToolInput once the typed-tool migration is complete
    def _parse_input(
        self, tool_input: str | dict[str, Any] | ChartToolInput
    ) -> ChartToolInput:
        if isinstance(tool_input, ChartToolInput):
            return tool_input

        raw_input = (
            parse_first_json(tool_input) if isinstance(tool_input, str) else tool_input
        )

        if isinstance(raw_input, dict) and "data" in raw_input:
            raw_input = {
                **raw_input,
                "data": _coerce_legacy_table_data(raw_input.get("data")),
            }

        return ChartToolInput.model_validate(raw_input)

    def _build_visualization(
        self,
        df: pd.DataFrame,
        chart_type: Literal["bar", "line"],
        x_column: str,
        y_column: str,
        title: str | None,
        color_column: str | None,
    ) -> go.Figure:
        if x_column not in df.columns:
            raise ValueError(
                f"x_column '{x_column}' not found in data. Available columns: {list(df.columns)}"
            )
        if y_column not in df.columns:
            raise ValueError(
                f"y_column '{y_column}' not found in data. Available columns: {list(df.columns)}"
            )

        if color_column:
            if color_column not in df.columns:
                logger.warning(
                    "color_column '%s' not found in data. Available columns: %s. Proceeding without color grouping.",
                    color_column,
                    list(df.columns),
                )
                color_column = None
            else:
                unique_values = df[color_column].nunique()
                logger.info(
                    "Multi-series chart: %s unique values in color_column '%s'",
                    unique_values,
                    color_column,
                )

        logger.info("=== Pre-Plot Validation ===")
        logger.info("Chart type: %s", chart_type)
        logger.info("X column: '%s' | Y column: '%s'", x_column, y_column)
        if color_column:
            logger.info("Color column: '%s' (multi-series)", color_column)
        logger.info("X data type: %s", df[x_column].dtype)
        logger.info("Y data type: %s", df[y_column].dtype)
        logger.info("X data sample (first 5): %s", df[x_column].head(5).tolist())
        logger.info("Y data sample (first 5): %s", df[y_column].head(5).tolist())

        if not pd.api.types.is_numeric_dtype(df[y_column]):
            logger.warning(
                "Y column '%s' is not numeric! Attempting conversion...", y_column
            )
            df[y_column] = pd.to_numeric(df[y_column], errors="coerce")
            logger.info("Conversion successful. New dtype: %s", df[y_column].dtype)

        try:
            y_min = df[y_column].min()
            y_max = df[y_column].max()
            y_mean = df[y_column].mean()
            logger.info("Y data range: %s to %s (mean: %.2f)", y_min, y_max, y_mean)
        except Exception as stat_error:
            logger.warning("Could not compute Y statistics: %s", stat_error)

        logger.info("DataFrame shape for plotting: %s", df.shape)
        logger.info("=== End Pre-Plot Validation ===\n")

        if chart_type == "bar":
            if color_column:
                fig = px.bar(
                    df, x=x_column, y=y_column, color=color_column, title=title
                )
            else:
                fig = px.bar(df, x=x_column, y=y_column, title=title)
                fig.update_traces(marker_color="#111184")
        elif chart_type == "line":
            if color_column:
                fig = px.line(
                    df, x=x_column, y=y_column, color=color_column, title=title
                )
            else:
                fig = px.line(df, x=x_column, y=y_column, title=title)
                fig.update_traces(line_color="#111184")
        else:
            raise ValueError(
                f"Unsupported chart type: {chart_type}. Supported types: bar, line"
            )

        fig.update_xaxes(tickangle=-45)
        return fig

    def _build_output_path(self, chart_type: str) -> Path:
        charts_dir = Path("data/charts")
        charts_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chart_{chart_type}_{timestamp}.png"
        return charts_dir / filename

    def _write_chart(self, fig: go.Figure, filepath: Path) -> str:
        try:
            fig.write_image(str(filepath), format="png", width=800, height=600)
            logger.info("Chart saved to %s", filepath)
            return f"Chart created successfully: {filepath}"
        except Exception as save_error:
            logger.error("Error saving chart: %s", save_error)
            html_path = filepath.with_suffix(".html")
            fig.write_html(str(html_path))
            return f"Chart saved as HTML: {html_path}"

    def render(self, tool_input: ChartToolInput) -> ChartOutput:
        if not isinstance(tool_input, ChartToolInput):
            raise TypeError(
                "ChartTool.render() requires a ChartToolInput instance. "
                "For string/JSON or dict inputs use the LangChain _run() entrypoint."
            )
        parsed_input = tool_input
        df = response_to_dataframe(parsed_input.data, reset_index=True)
        fig = self._build_visualization(
            df=df,
            chart_type=parsed_input.chart_type,
            x_column=parsed_input.x_column,
            y_column=parsed_input.y_column,
            title=parsed_input.title,
            color_column=parsed_input.color_column,
        )
        filepath = self._build_output_path(parsed_input.chart_type)

        try:
            fig.write_image(str(filepath), format="png", width=800, height=600)
            logger.info("Chart saved to %s", filepath)
            output_path = filepath
            mime_type = "image/png"
        except Exception as save_error:
            logger.error("Error saving chart: %s", save_error)
            output_path = filepath.with_suffix(".html")
            fig.write_html(str(output_path))
            mime_type = "text/html"

        return ChartOutput(
            spec=FinalChartSpec(
                type=parsed_input.chart_type,
                title=parsed_input.title,
            ),
            path=str(output_path),
            mime_type=mime_type,
        )

    def _execute(self, tool_input: str | dict[str, Any] | ChartToolInput) -> str:
        parsed_input = self._parse_input(tool_input)
        df = response_to_dataframe(parsed_input.data, reset_index=True)
        fig = self._build_visualization(
            df=df,
            chart_type=parsed_input.chart_type,
            x_column=parsed_input.x_column,
            y_column=parsed_input.y_column,
            title=parsed_input.title,
            color_column=parsed_input.color_column,
        )
        filepath = self._build_output_path(parsed_input.chart_type)
        return self._write_chart(fig, filepath)

    def _run(self, tool_input: str | dict[str, Any] | ChartToolInput) -> str:
        """Create a chart from the input data and save to data/charts/"""
        try:
            return self._execute(tool_input)
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return f"Error: {str(e)}"

    async def _arun(self, tool_input: str | dict[str, Any] | ChartToolInput) -> str:
        # FUTURE PHASE (PHASE 3): offload blocking `_run`/core (see sync+async PHASE block on `ChartTool`) — forwarding
        # here today keeps async callers on the blocking path deliberately until that work is prioritized.
        return self._run(tool_input)
