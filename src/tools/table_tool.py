import logging
import pandas as pd
from pathlib import Path
from typing import Any, Literal
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.domain.census_tool_contract import StrictCensusApiRawTable
from src.domain.final_output_contract import FinalTableSpec
from src.domain.rendered_output_contract import TableMimeType, TableOutput
from src.services.dataframe_utils import _create_dataframe_from_json
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


class TableToolInput(BaseModel):
    """Input for table creation"""

    model_config = ConfigDict(extra="forbid")

    format: Literal["csv", "excel", "html"] = Field(
        default="csv",
        description="Output format: 'csv' for simple export, 'excel' for Excel files, 'html' for web tables",
    )
    filename: str | None = Field(
        default=None, description="Optional custom filename (without extension)"
    )
    title: str | None = Field(
        default="Census Data Table", description="Table title/description"
    )
    data: StrictCensusApiRawTable = Field(
        ..., description="Census data dict from census_api_call tool"
    )


class TableTool(BaseTool):
    name: str = "create_table"
    description: str = "Export census data as formatted tables"
    model_config = ConfigDict(extra="forbid")

    # TODO: remove str and dict input types and replace with TableToolInput once the typed-tool migration is complete
    def _parse_input(
        self, tool_input: str | dict[str, Any] | TableToolInput
    ) -> TableToolInput:
        if isinstance(tool_input, TableToolInput):
            return tool_input

        raw_input = (
            parse_first_json(tool_input) if isinstance(tool_input, str) else tool_input
        )
        if isinstance(raw_input, dict) and "data" in raw_input:
            raw_input = {
                **raw_input,
                "data": _coerce_legacy_table_data(raw_input.get("data")),
            }

        return TableToolInput.model_validate(raw_input)

    # TODO: remove this function and replace it with a function that uses the StrictCensusApiRawTable model. See T2-CG-010.
    def _build_dataframe(self, data: StrictCensusApiRawTable) -> pd.DataFrame:
        return _create_dataframe_from_json({"data": [data.headers, *data.rows]})

    def _build_output_path(self, format_type: str, filename: str | None) -> Path:
        tables_dir = Path("data/tables")
        tables_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"table_{format_type}_{timestamp}"

        suffix_map = {
            "csv": ".csv",
            "excel": ".xlsx",
            "html": ".html",
        }
        return tables_dir / f"{filename}{suffix_map[format_type]}"

    def _write_table(
        self,
        df: pd.DataFrame,
        filepath: Path,
        format_type: str,
        title: str | None,
    ) -> None:
        if format_type == "csv":
            df.to_csv(filepath, index=False, encoding="utf-8")
        elif format_type == "excel":
            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Census Data", index=False)
        elif format_type == "html":
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>{title}</title></head>
            <body>
                <h1>{title}</h1>
                {df.to_html(index=False, escape=False, table_id="census-table")}
            </body>
            </html>
            """
            filepath.write_text(html_content, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def render(self, tool_input: TableToolInput) -> TableOutput:
        parsed_input = self._parse_input(tool_input)
        df = self._build_dataframe(parsed_input.data)
        filepath = self._build_output_path(parsed_input.format, parsed_input.filename)
        self._write_table(df, filepath, parsed_input.format, parsed_input.title)
        logger.info("Table saved to %s", filepath)

        mime_type_map: dict[Literal["csv", "excel", "html"], TableMimeType] = {
            "csv": "text/csv",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "html": "text/html",
        }

        return TableOutput(
            spec=FinalTableSpec(
                format=parsed_input.format,
                filename=parsed_input.filename,
                title=parsed_input.title,
            ),
            path=str(filepath),
            mime_type=mime_type_map[parsed_input.format],
        )

    # TODO: remove str and dict input types and replace with TableToolInput once the typed-tool migration is complete
    def _execute(self, tool_input: str | dict[str, Any] | TableToolInput) -> str:
        parsed_input = self._parse_input(tool_input)
        df = self._build_dataframe(parsed_input.data)
        filepath = self._build_output_path(parsed_input.format, parsed_input.filename)
        self._write_table(df, filepath, parsed_input.format, parsed_input.title)
        logger.info("Table saved to %s", filepath)
        return f"Table created successfully: {filepath}"

    def _run(self, tool_input: str | dict[str, Any] | TableToolInput) -> str:
        try:
            return self._execute(tool_input)
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            return f"Error: {str(e)}"

    async def _arun(self, tool_input: str | dict[str, Any] | TableToolInput) -> str:
        return self._run(tool_input)
