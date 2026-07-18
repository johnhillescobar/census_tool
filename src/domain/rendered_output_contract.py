from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class RenderedArtifactSuccess(BaseModel):
    """Successful chart/table export written to disk."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    kind: Literal["chart", "table"]
    path: str
    mime_type: str
    title: str | None = None


class RenderedArtifactFailure(BaseModel):
    """Chart/table could not be produced but should remain visible downstream."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["failure"] = "failure"
    kind: Literal["chart", "table"]
    error_code: str
    message: str
    title: str | None = None


GeneratedFileArtifact = Annotated[
    RenderedArtifactSuccess | RenderedArtifactFailure,
    Field(discriminator="status"),
]

_CHART_SUCCESS_PREFIXES = (
    "Chart created successfully: ",
    "Chart saved as HTML: ",
)
_TABLE_SUCCESS_PREFIX = "Table created successfully: "


def _mime_type_for_path(path: str, *, kind: Literal["chart", "table"]) -> str:
    lower = path.lower()
    if lower.endswith(".html"):
        return "text/html"
    if lower.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".png"):
        return "image/png"
    return "image/png" if kind == "chart" else "text/csv"


def artifact_from_tool_result(
    result: str,
    *,
    kind: Literal["chart", "table"],
    title: str | None = None,
) -> GeneratedFileArtifact:
    prefixes = _CHART_SUCCESS_PREFIXES if kind == "chart" else (_TABLE_SUCCESS_PREFIX,)
    for prefix in prefixes:
        if result.startswith(prefix):
            path = result.split(prefix, 1)[1]
            return RenderedArtifactSuccess(
                kind=kind,
                path=path,
                mime_type=_mime_type_for_path(path, kind=kind),
                title=title,
            )
    return RenderedArtifactFailure(
        kind=kind,
        error_code="RENDER_EXCEPTION",
        message=result,
        title=title,
    )


def artifact_to_display_text(artifact: GeneratedFileArtifact) -> str:
    if artifact.status == "success":
        return f"{artifact.kind.title()} created successfully: {artifact.path}"
    return f"{artifact.kind.title()} failed: {artifact.message}"
