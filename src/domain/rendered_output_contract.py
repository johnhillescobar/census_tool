from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec


TableMimeType = Literal[
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/html",
    "application/vnd.apache.parquet",
]
ChartMimeType = Literal["image/png", "text/html"]

FootnoteKind = Literal["source", "methodology", "warning", "disclaimer", "note"]

NarrativeFormat = Literal["plain_text", "markdown"]


class NarrativeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Primary narrative answer for the user.")
    format: NarrativeFormat = "plain_text"


class FootnoteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Footnote text shown to the user.")
    kind: FootnoteKind = "note"


class ChartOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: FinalChartSpec
    path: str
    mime_type: ChartMimeType


class TableOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: FinalTableSpec
    path: str
    mime_type: TableMimeType


class RenderedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["chart", "table"]
    path: str
    mime_type: str
    title: str | None = None
