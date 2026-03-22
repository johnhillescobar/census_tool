from typing import Any, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.comparison_plan import CensusDataset

CensusApiFailureCode = Literal[
    "INVALID_REQUEST",
    "HTTP_ERROR",
    "REQUEST_EXCEPTION",
    "MAX_RETRIES_EXCEEDED",
    "API_PAYLOAD_SHAPE_INVALID",
    "API_PAYLOAD_JSON_INVALID",
]


class CensusApiQueryParams(BaseModel):
    """
    Typed query params for Census API requests.
    Uses Census-native aliases: get / for / in.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    get_vars: list[str] = Field(..., alias="get")
    geo_for: str = Field(..., alias="for")
    geo_in: str | None = Field(default=None, alias="in")
    key: str | None = Field(default=None, min_length=40, max_length=40)

    @field_validator("get_vars", mode="before")
    @classmethod
    def split_vars(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    @field_validator("get_vars")
    @classmethod
    def validate_get_vars(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("get vars must be non-empty")
        normalized = [item.strip() for item in v]
        if any(not item for item in normalized):
            raise ValueError("get vars must not contain blank entries")
        if len(normalized) != len(set(normalized)):
            raise ValueError("get vars must be unique")
        return normalized

    @field_validator("geo_for")
    @classmethod
    def validate_geo_for(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("for must be non-empty")
        return value

    @field_validator("geo_in")
    @classmethod
    def validate_geo_in(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("in must be non-empty when provided")
        return value


class CensusDatasetUrl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: CensusDataset
    year: int = Field(..., ge=2000)
    root_url: AnyUrl

    @model_validator(mode="after")
    def validate_url_matches_dataset(self) -> "CensusDatasetUrl":
        # Keep this strict and transparent: expected path is /data/{year}/{dataset}
        expected_suffix = f"/data/{self.year}/{self.dataset}"
        url_text = str(self.root_url)
        if "api.census.gov" not in url_text:
            raise ValueError("dataset url host must be api.census.gov")
        if expected_suffix not in url_text:
            raise ValueError("dataset url does not match year/dataset contract")
        return self


class CensusApiRawTable(BaseModel):
    """
    Census API payload shape: [[headers], [row1], [row2], ...]
    """

    model_config = ConfigDict(extra="forbid")

    headers: list[str]
    rows: list[list[str]]

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("headers must be non-empty")
        return [str(item) for item in v]

    @field_validator("rows")
    @classmethod
    def validate_rows_non_empty(cls, v: list[list[str]]) -> list[list[str]]:
        # Keep empty rows valid for clients that want to signal EMPTY_RESULT downstream.
        return [[str(item) for item in row] for row in v]

    @model_validator(mode="after")
    def validate_row_width(self) -> "CensusApiRawTable":
        width = len(self.headers)
        for idx, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(f"row {idx} has {len(row)} values, expected {width}")
        return self

    @classmethod
    def from_api_payload(cls, raw: list[Any]) -> "CensusApiRawTable":
        if not raw or not isinstance(raw, list) or not isinstance(raw[0], list):
            raise ValueError("Census API response must be a non-empty list of lists")
        headers = [str(cell) for cell in raw[0]]
        rows = [[str(cell) for cell in row] for row in raw[1:]]
        return cls(headers=headers, rows=rows)

    def to_records(self) -> list[dict[str, str]]:
        return [dict(zip(self.headers, row)) for row in self.rows]


class CensusApiCallSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    url: str
    attempt: int
    table: CensusApiRawTable


class CensusApiCallFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["failure"] = "failure"
    url: str
    attempt: int
    error_code: CensusApiFailureCode
    error_message: str


class CensusApiCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: CensusApiCallSuccess | None = None
    failure: CensusApiCallFailure | None = None

    @model_validator(mode="after")
    def validate_xor(self) -> "CensusApiCallResult":
        has_success = self.success is not None
        has_failure = self.failure is not None
        if has_success == has_failure:
            raise ValueError("exactly one of success/failure must be set")
        return self
