from pydantic import BaseModel, ConfigDict, Field
from src.domain.comparison_plan import ComparisonPlan, DerivedMetric


class ComparisonInputRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    geo_id: str
    metric: str
    value: float
    benchmark_value: float


class ComparisonMetricComputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ComparisonPlan
    rows: list[ComparisonInputRow]


class ComparisonMetricRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., description="The year of the metric.")
    geo_id: str = Field(..., description="The geo_id of the metric.")
    metric: str = Field(..., description="The metric of the metric.")
    derived_metric: DerivedMetric = Field(
        ..., description="The derived metric of the metric."
    )
    value: float | None = Field(default=None, description="The value of the metric.")
    subject_value: float | None = Field(
        default=None, description="The subject value of the metric."
    )
    benchmark_value: float | None = Field(
        default=None, description="The benchmark value of the metric."
    )
    note: str | None = Field(None, description="The note of the metric.")
    error: str | None = Field(None, description="The error of the metric.")
    success: bool = Field(
        default=True, description="Whether the metric computation was successful."
    )
