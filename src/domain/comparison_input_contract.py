from pydantic import BaseModel, ConfigDict, Field


class ComparisonInputRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., description="The year of the metric.")
    geo_id: str = Field(..., description="The geo_id of the metric.")
    metric: str = Field(..., description="The metric of the metric.")
    value: float = Field(..., description="The subject value of the metric.")
    benchmark_value: float = Field(
        ..., description="The benchmark value of the metric."
    )
