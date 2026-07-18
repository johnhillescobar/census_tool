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


def artifact_from_tool_result(
    result: str,
    *,
    kind: Literal["chart", "table"],
    title: str | None = None,
) -> GeneratedFileArtifact:
    success_prefix = (
        "Chart created successfully: "
        if kind == "chart"
        else "Table created successfully: "
    )
    if result.startswith(success_prefix):
        path = result.split(success_prefix, 1)[1]
        return RenderedArtifactSuccess(
            kind=kind,
            path=path,
            mime_type="image/png" if kind == "chart" else "text/csv",
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
