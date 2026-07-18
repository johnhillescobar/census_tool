from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .benchmark_contract import (
    ComparisonOp,
    GeographyLevel,
    NormalizationMode,
)
from .temporal_contract import (
    MissingYearPolicy,
)

CensusDataset = Literal[
    "acs/acs5",
    "acs/acs5/profile",
    "acs/acs5/cprofile",
    "acs/acs5/spp",
    "acs/acs5/subject",
    "acs/acs1",
    "acs/acs1/profile",
    "acs/acs1/cprofile",
    "acs/acs1/spp",
    "acs/acs1/subject",
]

DerivedMetric = Literal["difference", "pct_difference", "rank", "percentile", "trend_gap"]

JoinKey = Literal["year", "geo_id"]


class ComparisonPlan(BaseModel):
    """Use fields that map directly from your current Temporal+Benchmark contracts"""

    model_config = ConfigDict(extra="forbid")

    query_years: list[int] = Field(..., description="The years to the census query.")
    dataset: CensusDataset = Field(..., description="The census dataset to query.")
    metric: str = Field(..., description="The metric to query.")
    subject_geo_level: GeographyLevel = Field(..., description="The level of the subject geography.")
    subject_geos: list[str] = Field(..., description="The list of subject geographies.")
    benchmark_geo_level: GeographyLevel | None = Field(default=None, description="The level of the benchmark geography.")
    benchmark_geos: list[str] = Field(default_factory=list, description="The list of benchmark geographies.")
    comparison_op: ComparisonOp = Field(..., description="The comparison operator.")
    normalization: NormalizationMode = Field(..., description="The normalization mode.")
    missing_year_policy: MissingYearPolicy = Field(..., description="The policy for handling missing years.")
    derived_metrics: list[DerivedMetric] = Field(..., description="The derived metrics to calculate.")
    join_keys: list[JoinKey] = Field(..., description="The keys to join on.")
    requested_text: str | None = Field(default=None, description="The text that the user requested.")

    @field_validator("query_years")
    def validate_query_years(cls, v: list[int]) -> list[int]:
        if len(v) == 0:
            raise ValueError("query_years must be non-empty")
        if len(v) != len(set(v)):
            raise ValueError("query_years must be unique")
        return sorted(v)

    @field_validator("benchmark_geos")
    def validate_benchmark_geos(cls, v: list[str]) -> list[str]:
        return v

    @field_validator("subject_geos")
    def validate_subject_geos(cls, v: list[str]) -> list[str]:
        if len(v) == 0:
            raise ValueError("subject_geos must be non-empty")
        return v

    @field_validator("metric")
    def validate_metric(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("metric must be non-empty")
        return v

    @field_validator("derived_metrics")
    def validate_derived_metrics(cls, v: list[DerivedMetric]) -> list[DerivedMetric]:
        if len(v) == 0:
            raise ValueError("derived_metrics must be non-empty")
        if len(v) != len(set(v)):
            raise ValueError("derived_metrics must be unique")
        return v

    @field_validator("join_keys")
    def validate_join_keys(cls, v: list[JoinKey]) -> list[JoinKey]:
        if len(v) == 0:
            raise ValueError("join_keys must be non-empty")
        if len(v) != len(set(v)):
            raise ValueError("join_keys must be unique")
        return v

    @model_validator(mode="after")
    def validate_fields(self) -> "ComparisonPlan":
        # Cross-field rule for benchmark target consistency:
        # - if no benchmark_geo_level, benchmark_geos must be empty
        # - if benchmark_geo_level is set, benchmark_geos must be non-empty
        if self.benchmark_geo_level is None and self.benchmark_geos:
            raise ValueError("benchmark_geos must be empty when benchmark_geo_level is None")
        if self.benchmark_geo_level is not None and not self.benchmark_geos:
            raise ValueError("benchmark_geos must be non-empty when benchmark_geo_level is provided")

        # subject_geo_level is required by type; keep this explicit defensive check
        if not self.subject_geos:
            raise ValueError("subject_geos must be non-empty when subject_geo_level is provided")

        return self

    @field_serializer("query_years")
    def serialize_query_years(self, v: list[int]) -> list[int]:
        return sorted(v)
