from pydantic import BaseModel, ConfigDict, Field, model_validator

from .benchmark_contract import BenchmarkIntent
from .comparison_plan import ComparisonPlan
from .geography_contract import GeographyIntent
from .temporal_contract import TemporalIntent


class AgentPlanContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geography: GeographyIntent | None = Field(
        default=None, description="Resolved geography from planning nodes."
    )
    temporal: TemporalIntent | None = Field(
        default=None, description="Resolved temporal intent from planning nodes."
    )
    benchmark: BenchmarkIntent | None = Field(
        default=None, description="Resolved benchmark intent from planning nodes."
    )
    comparison: ComparisonPlan | None = Field(
        default=None, description="Resolved comparison plan from planning nodes."
    )
    has_comparison_plan: bool = Field(
        ..., description="Whether a comparison plan is active for this query."
    )

    @model_validator(mode="after")
    def validate_comparison_consistency(self) -> "AgentPlanContext":
        if self.has_comparison_plan and self.comparison is None:
            raise ValueError(
                "comparison must be provided when has_comparison_plan is True"
            )
        if not self.has_comparison_plan and self.comparison is not None:
            raise ValueError(
                "comparison must be null when has_comparison_plan is False"
            )
        if self.has_comparison_plan and (
            self.temporal is None or self.benchmark is None
        ):
            raise ValueError(
                "temporal and benchmark must be provided when has_comparison_plan is True"
            )
        if self.temporal is None and self.benchmark is None and self.comparison is None:
            raise ValueError("At least one planning artifact must be provided")
        return self
