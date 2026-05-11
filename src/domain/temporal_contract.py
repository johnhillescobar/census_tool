from typing import Annotated, Literal, Union
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
    start_year: int | None = Field(
        None, description="The start year of the temporal intent."
    )
    end_year: int | None = Field(
        None, description="The end year of the temporal intent."
    )
    anchor_year: int | None = Field(
        None, description="The anchor year of the temporal intent."
    )
    rolling_window_years: int | None = Field(
        None, description="The number of years in a rolling temporal window."
    )
    missing_year_policy: MissingYearPolicy = Field(
        default="skip_with_note", description="The policy for handling missing years."
    )
    requested_text: str | None = Field(
        None, description="The text that the user requested."
    )

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "TemporalIntent":
        if self.mode != "rolling" and self.rolling_window_years is not None:
            raise ValueError("rolling_window_years is only allowed for rolling mode.")

        if self.mode == "point_in_time":
            if self.anchor_year is None:
                raise ValueError("Anchor year is required for point in time mode.")
            if self.start_year is not None or self.end_year is not None:
                raise ValueError(
                    "Start year and end year are not allowed for point in time mode."
                )

        elif self.mode == "range":
            if self.start_year is None or self.end_year is None:
                raise ValueError("Start year and end year are required for range mode.")
            if self.start_year > self.end_year:
                raise ValueError("start_year must be <= end_year for range mode.")

        elif self.mode == "rolling":
            if self.rolling_window_years is None:
                raise ValueError("rolling_window_years is required for rolling mode.")
            if self.rolling_window_years <= 0:
                raise ValueError("rolling_window_years must be > 0 for rolling mode.")
            if any(
                v is not None
                for v in [self.start_year, self.end_year, self.anchor_year]
            ):
                raise ValueError(
                    "start_year/end_year/anchor_year must be null for rolling mode."
                )

        elif self.mode == "latest_available":
            if any(
                v is not None
                for v in [self.start_year, self.end_year, self.anchor_year]
            ):
                raise ValueError(
                    "start_year/end_year/anchor_year must be null for latest_available mode."
                )

        elif self.mode == "multi_period_compare":
            if self.start_year is None or self.end_year is None:
                raise ValueError(
                    "Start year and end year are required for multi period compare mode."
                )
            if self.start_year > self.end_year:
                raise ValueError(
                    "start_year must be <= end_year for multi period compare mode."
                )

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
    status: Literal["resolved"] = Field(
        default="resolved", description="The status of the temporal resolution."
    )
    time: TemporalIntent = Field(
        ..., description="The temporal intent that was resolved."
    )


class TemporalClarificationRequired(BaseModel):
    status: Literal["clarification_required"] = Field(
        default="clarification_required",
        description="The status of the temporal clarification required.",
    )
    reason_code: str = Field(
        ..., description="The reason code for the temporal clarification required."
    )
    clarification_prompt: ClarificationPrompt = Field(
        ...,
        description="The clarification prompt for the temporal clarification required.",
    )


TemporalResolution = Annotated[
    Union[TemporalResolved, TemporalClarificationRequired],
    Field(discriminator="status"),
]
