from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.retrieval_plan import RetrievalEvidence, ValidationFailure
from src.services.grounded_plan_validator import CanonicalTable, ValidatedGroundedPlan

from .benchmark_contract import BenchmarkIntent
from .comparison_plan import ComparisonPlan
from .geography_contract import GeographyIntent
from .temporal_contract import TemporalIntent


class AgentPlanContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geography: GeographyIntent | None = Field(default=None, description="Resolved geography from planning nodes.")
    temporal: TemporalIntent | None = Field(default=None, description="Resolved temporal intent from planning nodes.")
    benchmark: BenchmarkIntent | None = Field(default=None, description="Resolved benchmark intent from planning nodes.")
    comparison: ComparisonPlan | None = Field(default=None, description="Resolved comparison plan from planning nodes.")
    selected_table: CanonicalTable | None = Field(default=None, description="Validated Chroma-selected Census table.")
    grounded_plan: ValidatedGroundedPlan | None = Field(default=None, description="Validated grounded execution plan.")
    has_comparison_plan: bool = Field(..., description="Whether a comparison plan is active for this query.")
    plan_validation_failures: list[ValidationFailure] = Field(
        default_factory=list,
        description="Validator failures from the prior planning attempt (retry turns only).",
    )
    prior_retrieval_evidence: list[RetrievalEvidence] = Field(
        default_factory=list,
        description="Retrieval evidence preserved from prior planning attempts.",
    )
    plan_validation_attempt: int = Field(
        default=0,
        description="Number of validator rejections so far (0 on first planning turn).",
    )

    @model_validator(mode="after")
    def validate_comparison_consistency(self) -> "AgentPlanContext":
        if self.has_comparison_plan and self.comparison is None:
            raise ValueError("comparison must be provided when has_comparison_plan is True")
        if not self.has_comparison_plan and self.comparison is not None:
            raise ValueError("comparison must be null when has_comparison_plan is False")
        if self.has_comparison_plan and (self.temporal is None or self.benchmark is None):
            raise ValueError("temporal and benchmark must be provided when has_comparison_plan is True")
        if self.temporal is None and self.benchmark is None and self.comparison is None:
            raise ValueError("At least one planning artifact must be provided")
        return self
