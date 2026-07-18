from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

GeographySource = Literal[
    "explicit",
    "profile_default",
    "missing_geo_default",
]

GeographyLevel = Literal[
    "nation",
    "state",
    "county",
    "place",
    "cbsa",
]


class GeographyIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: GeographyLevel
    geo_for: dict[str, str] = Field(default_factory=dict)
    geo_in: dict[str, str] = Field(default_factory=dict)
    display_name: str
    source: GeographySource
    requested_text: str | None = None


class ClarificationOption(BaseModel):
    option_id: str
    label: str


class ClarificationPrompt(BaseModel):
    template_id: str
    reason_code: str
    question_text: str
    options: list[ClarificationOption]
    expected_response_shape: Literal["single_select"] = "single_select"


class GeographyResolved(BaseModel):
    status: Literal["resolved"] = "resolved"
    geography: GeographyIntent


class GeographyClarificationRequired(BaseModel):
    status: Literal["clarification_required"] = "clarification_required"
    reason_code: str
    clarification_prompt: ClarificationPrompt


GeographyResolution = Annotated[
    GeographyResolved | GeographyClarificationRequired,
    Field(discriminator="status"),
]
