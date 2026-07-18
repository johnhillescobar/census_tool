from pydantic import BaseModel, ConfigDict, Field

from src.domain.comparison_plan import ComparisonPlan, DerivedMetric

METRIC_VARIABLE_MAP: dict[str, str] = {
    "population": "B01003_001E",
    "median_income": "B19013_001E",
    "unemployment": "B23025_005E",
}


class ComparisonInputRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    geo_id: str
    metric: str
    value: float
    benchmark_value: float


class ComparisonCensusObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    geo_id: str
    metric: str
    value: float
    geo_level: str | None = Field(default=None, description="Optional geography level for the observation.")


class ComparisonInputRowBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ComparisonPlan
    observations: list[ComparisonCensusObservation]


class ComparisonInputRowsArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[ComparisonInputRow]


class ComparisonMetricArtifactRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    geo_id: str
    metric: str
    derived_metric: DerivedMetric
    value: float | None = None
    subject_value: float | None = None
    benchmark_value: float | None = None
    note: str | None = None
    error: str | None = None
    success: bool = True


class ComparisonMetricsArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[ComparisonMetricArtifactRow]
