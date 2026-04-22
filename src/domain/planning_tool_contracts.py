from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.comparison_plan import CensusDataset


GeographyValidationErrorCode = Literal[
    "INVALID_INPUT_SCHEMA",
    "VALIDATION_RUNTIME_ERROR",
]

VariableValidationAction = Literal["validate_variables", "list_variables"]
VariableValidationErrorCode = Literal[
    "INVALID_INPUT_SCHEMA",
    "VARIABLE_LOOKUP_FAILED",
]


def _normalize_geo_mapping(value: dict[str, str]) -> dict[str, str]:
    if not value:
        raise ValueError("mapping must be non-empty")

    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = key.strip()
        normalized_item = item.strip()
        if not normalized_key or not normalized_item:
            raise ValueError("mapping keys and values must be non-empty")
        normalized[normalized_key] = normalized_item
    return normalized


class GeographyValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: CensusDataset = Field(..., description="The dataset to validate against.")
    year: int = Field(..., description="The Census year to validate against.")
    geo_for: dict[str, str] = Field(..., description="The Census geo_for clause.")
    geo_in: dict[str, str] = Field(
        default_factory=dict, description="The optional Census geo_in clause."
    )

    @field_validator("year")
    def validate_year(cls, value: int) -> int:
        if value < 2000:
            raise ValueError("year must be greater than or equal to 2000")
        return value

    @field_validator("geo_for")
    def validate_geo_for(cls, value: dict[str, str]) -> dict[str, str]:
        return _normalize_geo_mapping(value)

    @field_validator("geo_in")
    def validate_geo_in(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            return {}
        return _normalize_geo_mapping(value)


class GeographyValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="Whether the tool executed successfully.")
    request: GeographyValidationRequest | None = Field(
        ..., description="The validated request payload."
    )
    is_valid: bool = Field(..., description="Whether the geography payload is valid.")
    repaired_for: dict[str, str] = Field(default_factory=dict)
    repaired_in: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    error: GeographyValidationErrorCode | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "GeographyValidationResponse":
        if self.success:
            if self.request is None:
                raise ValueError("request must be present when success is True")
            if self.error is not None or self.error_message is not None:
                raise ValueError(
                    "error and error_message must be None when success is True"
                )
            if self.is_valid and self.errors:
                raise ValueError("errors must be empty when is_valid is True")
            if not self.is_valid and not self.errors:
                raise ValueError("errors must be present when is_valid is False")
            return self

        if self.error is None or self.error_message is None:
            raise ValueError(
                "error and error_message are required when success is False"
            )
        if self.is_valid:
            raise ValueError("is_valid must be False when success is False")
        if self.request is None and self.error != "INVALID_INPUT_SCHEMA":
            raise ValueError(
                "request must be present on runtime failures unless schema parsing failed"
            )
        return self


class VariableMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str = ""
    label: str = ""
    universe: str = ""
    dataset: str = ""


class VariableListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    var: str
    label: str = ""
    concept: str = ""
    universe: str = ""


class VariableValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: VariableValidationAction = Field(
        default="validate_variables",
        description="Whether to validate explicit variables or list candidate variables.",
    )
    dataset: CensusDataset = Field(..., description="The dataset to validate against.")
    year: int = Field(..., description="The Census year to validate against.")
    variables: list[str] | None = Field(
        default=None, description="Variables to validate for validate_variables."
    )
    table_code: str | None = Field(
        default=None, description="Optional table prefix for list_variables."
    )
    concept: str | None = Field(
        default=None, description="Optional concept filter for list_variables."
    )
    limit: int = Field(default=20, description="Maximum list_variables results.")

    @field_validator("year")
    def validate_year(cls, value: int) -> int:
        if value < 2000:
            raise ValueError("year must be greater than or equal to 2000")
        return value

    @field_validator("variables")
    def validate_variables(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        normalized = [item.strip() for item in value if item and item.strip()]
        if not normalized:
            raise ValueError("variables must be non-empty when provided")
        if len(normalized) != len(set(normalized)):
            raise ValueError("variables must be unique")
        return normalized

    @field_validator("table_code", "concept")
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("limit")
    def validate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be greater than or equal to 1")
        return value

    @model_validator(mode="after")
    def validate_action_requirements(self) -> "VariableValidationRequest":
        if self.action == "validate_variables" and not self.variables:
            raise ValueError(
                "variables field is required for validate_variables action"
            )
        return self


class VariableValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="Whether the tool executed successfully.")
    request: VariableValidationRequest | None = Field(
        ..., description="The validated request payload."
    )
    action: VariableValidationAction = Field(..., description="The executed action.")
    valid: list[str] = Field(default_factory=list)
    invalid: list[str] = Field(default_factory=list)
    years_available: dict[str, list[str]] = Field(default_factory=dict)
    details: dict[str, VariableMetadata] = Field(default_factory=dict)
    alternatives: dict[str, list[str]] = Field(default_factory=dict)
    source: dict[str, str] = Field(default_factory=dict)
    count: int = 0
    variables: list[VariableListItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: VariableValidationErrorCode | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "VariableValidationResponse":
        if self.success:
            if self.request is None:
                raise ValueError("request must be present when success is True")
            if self.error is not None or self.error_message is not None:
                raise ValueError(
                    "error and error_message must be None when success is True"
                )
            if self.action == "list_variables" and self.count != len(self.variables):
                raise ValueError("count must equal len(variables) for list_variables")
            return self

        if self.error is None or self.error_message is None:
            raise ValueError(
                "error and error_message are required when success is False"
            )
        if self.request is None and self.error != "INVALID_INPUT_SCHEMA":
            raise ValueError(
                "request must be present on runtime failures unless schema parsing failed"
            )
        return self
