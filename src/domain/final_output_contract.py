from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class FinalChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bar", "line"] = Field(
        ..., description="Chart type requested for output rendering."
    )
    title: str | None = Field(
        default=None, description="Optional human-readable chart title."
    )

    @field_validator("title")
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class FinalTableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["csv", "excel", "html"] = Field(
        default="csv", description="Requested table export format."
    )
    filename: str | None = Field(default=None, description="Optional output filename.")
    title: str | None = Field(default=None, description="Optional table title.")

    @field_validator("filename", "title")
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)
