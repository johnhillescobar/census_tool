from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TemporalMode = Literal[
    "point_in_time",
    "range",
    "rolling",
    "latest_available",
    "multi_period_compare",
]

MissingYearPolicy = Literal["skip_with_note", "fail_closed"]


class TemporalIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TemporalMode
    start_year: int | None = Field(None, description="The start year of the temporal intent.")
    end_year: int | None = Field(None, description="The end year of the temporal intent.")
    anchor_year: int | None = Field(None, description="The anchor year of the temporal intent.")
    missing_year_policy: MissingYearPolicy = Field(
        default="skip_with_note", description="The policy for handling missing years."
    )
    requested_text: str | None = Field(None, description="The text that the user requested.")

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "TemporalIntent":
        if self.mode == "point_in_time":
            if self.anchor_year is None:
                raise ValueError("Anchor year is required for point in time mode.")
            if self.start_year is not None or self.end_year is not None:
                raise ValueError("Start year and end year are not allowed for point in time mode.")

        elif self.mode == "range":
            if self.start_year is None or self.end_year is None:
                raise ValueError("Start year and end year are required for range mode.")
            if self.start_year > self.end_year:
                raise ValueError("start_year must be <= end_year for range mode.")

        elif self.mode == "rolling":
            # Keep loose for now until final TemporalIntent lands.
            # You can enforce a rolling_window_years field later.
            pass

        elif self.mode == "latest_available":
            if any(v is not None for v in [self.start_year, self.end_year, self.anchor_year]):
                raise ValueError("start_year/end_year/anchor_year must be null for latest_available mode.")

        elif self.mode == "multi_period_compare":
            if self.start_year is None or self.end_year is None:
                raise ValueError("Start year and end year are required for multi period compare mode.")
            if self.start_year > self.end_year:
                raise ValueError("start_year must be <= end_year for multi period compare mode.")

        return self


class ClarificationOption(BaseModel):
    option_id: str
    label: str


class ClarificationPrompt(BaseModel):
    template_id: str
    reason_code: str
    question_text: str
    options: list[ClarificationOption]
    expected_response_shape: Literal["single_select"] = Field(
        default="single_select", description="The shape of the expected response."
    )


class TemporalResolved(BaseModel):
    status: Literal["resolved"] = Field(default="resolved", description="The status of the temporal resolution.")
    time: TemporalIntent = Field(..., description="The temporal intent that was resolved.")


class TemporalClarificationRequired(BaseModel):
    status: Literal["clarification_required"] = Field(
        default="clarification_required",
        description="The status of the temporal clarification required.",
    )
    reason_code: str = Field(..., description="The reason code for the temporal clarification required.")
    clarification_prompt: ClarificationPrompt = Field(
        ...,
        description="The clarification prompt for the temporal clarification required.",
    )


TemporalResolution = Annotated[
    TemporalResolved | TemporalClarificationRequired,
    Field(discriminator="status"),
]
