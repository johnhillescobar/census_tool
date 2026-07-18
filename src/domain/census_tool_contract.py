from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.comparison_plan import CensusDataset

SUPPORTED_DATASETS = set(get_args(CensusDataset))

StrictCensusApiErrorCode = Literal[
    "INVALID_INPUT_SCHEMA",
    "NO_STRICT_CENSUS_PAYLOAD",
    "INVALID_GEO_PARAMS",
    "UNSUPPORTED_DATASET",
    "UNSUPPORTED_YEAR",
    "API_HTTP_ERROR",
    "API_PAYLOAD_SHAPE_INVALID",
    "EMPTY_RESULT",
]

ERROR_CODE_TO_MESSAGE = {
    "INVALID_INPUT_SCHEMA": "The input schema is invalid",
    "NO_STRICT_CENSUS_PAYLOAD": "No validated strict Census API payload is attached",
    "INVALID_GEO_PARAMS": "The geography parameters are invalid",
    "UNSUPPORTED_DATASET": "The dataset is not supported",
    "UNSUPPORTED_YEAR": "The year is not supported",
    "API_HTTP_ERROR": "The API HTTP error occurred",
    "API_PAYLOAD_SHAPE_INVALID": "The API payload shape is invalid",
    "EMPTY_RESULT": "The result is empty",
}


class StrictCensusApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., description="The year to query.")
    dataset: CensusDataset = Field(..., description="The dataset to query.")
    variables: list[str] = Field(..., description="The variables to query.")
    geo_for: dict[str, str] = Field(..., description="The geography for clause.")
    geo_in: dict[str, str] | None = Field(
        default=None, description="The geography in clause."
    )
    geo_in_chained: list[dict[str, str]] = Field(
        default_factory=list, description="The geography in chained clause."
    )

    @field_validator("variables")
    def validate_variables(cls, v: list[str]) -> list[str]:
        if len(v) == 0:
            raise ValueError("variables must be non-empty")
        normalized = [item.strip() for item in v]
        if any(not item for item in normalized):
            raise ValueError("variables must not contain blank entries")
        if len(normalized) != len(set(normalized)):
            raise ValueError("variables must be unique")
        return normalized

    @field_validator("geo_for")
    def validate_geo_for(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) == 0:
            raise ValueError("geo_for must be non-empty")
        normalized: dict[str, str] = {}
        for key, value in v.items():
            k = key.strip()
            val = value.strip()
            if not k or not val:
                raise ValueError("geo_for keys/values must be non-empty")
            normalized[k] = val
        return normalized

    @field_validator("geo_in")
    def validate_geo_in(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return None
        normalized: dict[str, str] = {}
        for key, value in v.items():
            k = key.strip()
            val = value.strip()
            if not k or not val:
                raise ValueError("geo_in keys/values must be non-empty")
            normalized[k] = val
        return normalized

    @field_validator("geo_in_chained")
    def validate_geo_in_chained(cls, v: list[dict[str, str]]) -> list[dict[str, str]]:
        normalized_chain: list[dict[str, str]] = []
        for in_dict in v:
            if not in_dict:
                raise ValueError("geo_in_chained entries must be non-empty dicts")
            normalized_in: dict[str, str] = {}
            for key, value in in_dict.items():
                k = key.strip()
                val = value.strip()
                if not k or not val:
                    raise ValueError("geo_in_chained keys/values must be non-empty")
                normalized_in[k] = val
            normalized_chain.append(normalized_in)
        return normalized_chain

    @field_validator("year")
    def validate_year(cls, v: int) -> int:
        if v < 2000:
            raise ValueError("year must be greater than or equal to 2000")
        return v

    @field_validator("dataset")
    def validate_dataset(cls, v: CensusDataset) -> CensusDataset:
        if v not in SUPPORTED_DATASETS:
            raise ValueError(f"dataset {v} is not supported")
        return v


class StrictCensusApiRawTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: list[str] = Field(..., description="The headers of the table.")
    rows: list[list[str]] = Field(..., description="The rows of the table.")

    @field_validator("headers")
    def validate_headers(cls, v: list[str]) -> list[str]:
        if len(v) == 0:
            raise ValueError("headers must be non-empty")
        return v

    @field_validator("rows")
    def validate_rows(cls, v: list[list[str]]) -> list[list[str]]:
        if len(v) == 0:
            raise ValueError("rows must be non-empty")
        return v

    @model_validator(mode="after")
    def validate_row_width(self) -> "StrictCensusApiRawTable":
        header_len = len(self.headers)
        for row in self.rows:
            if len(row) != header_len:
                raise ValueError("rows must have the same length")
        return self


class StrictCensusApiRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, str] = Field(..., description="The values of the record.")

    @field_validator("values")
    def validate_values(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) == 0:
            raise ValueError("record values must be non-empty")
        normalized: dict[str, str] = {}
        for key, value in v.items():
            k = key.strip()
            val = value.strip()
            if not k:
                raise ValueError("record keys must be non-empty")
            normalized[k] = val
        return normalized


class StrictCensusApiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="Whether the request was successful.")
    request: StrictCensusApiRequest | None = Field(
        ...,
        description="The validated request that was made (None when schema parsing fails).",
    )
    headers: list[str] = Field(..., description="The headers of the table.")
    records: list[StrictCensusApiRecord] = Field(
        ..., description="The records of the table."
    )
    row_count: int = Field(..., description="The number of rows in the table.")
    error: StrictCensusApiErrorCode | None = Field(
        default=None, description="The error code that occurred."
    )
    error_message: str | None = Field(
        default=None, description="The error message that occurred."
    )

    @model_validator(mode="after")
    def validate_success(self) -> "StrictCensusApiResponse":
        if self.success:
            if self.request is None:
                raise ValueError("request must be present when success is True")
            if self.error is not None:
                raise ValueError("error must be None when success is True")
            if self.error_message is not None:
                raise ValueError("error_message must be None when success is True")
            if self.row_count != len(self.records):
                raise ValueError(
                    "row_count must equal len(records) when success is True"
                )
            if len(self.headers) == 0:
                raise ValueError("headers must be non-empty when success is True")
            return self

        # failure path
        if self.error is None:
            raise ValueError("error is required when success is False")
        if self.error == "NO_STRICT_CENSUS_PAYLOAD" and self.request is not None:
            raise ValueError(
                "request must be None when error is NO_STRICT_CENSUS_PAYLOAD"
            )
        allow_missing_request = self.error in (
            "INVALID_INPUT_SCHEMA",
            "NO_STRICT_CENSUS_PAYLOAD",
        )
        if self.request is None and not allow_missing_request:
            raise ValueError(
                "request must be present when success is False unless error is "
                "INVALID_INPUT_SCHEMA or NO_STRICT_CENSUS_PAYLOAD"
            )
        if self.error_message is None:
            self.error_message = ERROR_CODE_TO_MESSAGE[self.error]
        if len(self.headers) != 0:
            raise ValueError("headers must be empty when success is False")
        if len(self.records) != 0:
            raise ValueError("records must be empty when success is False")
        if self.row_count != 0:
            raise ValueError("row_count must be 0 when success is False")
        return self


def no_strict_census_payload(error_message: str | None = None) -> StrictCensusApiResponse:
    """Canonical failure shape when no strict tool success is available (Option B)."""
    return StrictCensusApiResponse(
        success=False,
        request=None,
        headers=[],
        records=[],
        row_count=0,
        error="NO_STRICT_CENSUS_PAYLOAD",
        error_message=error_message,
    )
