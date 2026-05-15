from typing import Annotated, Literal, TypeAlias

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


# --- Typed generated-file artifacts (Track 2C): success vs failure ---

RENDER_ERROR_NO_TABULAR_DATA = "NO_TABULAR_DATA"
RENDER_ERROR_RENDER_EXCEPTION = "RENDER_EXCEPTION"


class RenderedArtifactSuccess(BaseModel):
    """Successful chart/table export written to disk."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    kind: Literal["chart", "table"]
    path: str
    mime_type: str
    title: str | None = None


class RenderedArtifactFailure(BaseModel):
    """Chart/table could not be produced; surfaced to CLI/Streamlit/PDF."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["failure"] = "failure"
    kind: Literal["chart", "table"]
    error_code: str
    message: str
    title: str | None = None


GeneratedFileArtifact: TypeAlias = Annotated[
    RenderedArtifactSuccess | RenderedArtifactFailure,
    Field(discriminator="status"),
]


# Legacy name: callers constructing success rows use ``RenderedArtifact`` / ``RenderedArtifactSuccess``.
RenderedArtifact = RenderedArtifactSuccess
