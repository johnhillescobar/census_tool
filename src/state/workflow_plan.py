from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.domain.benchmark_contract import (
    BenchmarkIntent,
    BenchmarkResolution,
    BenchmarkResolved,
)
from src.domain.comparison_plan import ComparisonPlan
from src.domain.geography_contract import GeographyIntent, GeographyResolution
from src.domain.retrieval_plan import RetrievalEvidence
from src.domain.retrieval_trace import RetrievalTrace
from src.domain.temporal_contract import (
    TemporalIntent,
    TemporalResolution,
    TemporalResolved,
)
from src.services.grounded_plan_validator import CanonicalTable, ValidatedGroundedPlan


class BenchmarkNotApplicable(BaseModel):
    status: Literal["not_applicable"] = "not_applicable"
    reason: str


BenchmarkPlanState = Annotated[
    BenchmarkResolution | BenchmarkNotApplicable,
    Field(discriminator="status"),
]


GeographyClarificationSlot = Literal["table", "hierarchy", "area", "geography"]


class PendingGeographyOption(BaseModel):
    option_id: str
    candidate_id: str
    label: str


class PendingGeographyClarification(BaseModel):
    original_query: str
    trace_id: str
    retrieved_candidate_ids: list[str] = Field(default_factory=list)
    options: list[PendingGeographyOption] = Field(default_factory=list)
    requested_slot: GeographyClarificationSlot
    index_version: str | None = None
    reason_code: str


class WorkflowPlan(BaseModel):
    geography: GeographyResolution | None = None
    temporal: TemporalResolution | None = None
    benchmark: BenchmarkPlanState | None = None
    comparison: ComparisonPlan | None = None
    selected_table: CanonicalTable | None = None
    retrieval_evidence: list[RetrievalEvidence] = Field(default_factory=list)
    grounded_plan: ValidatedGroundedPlan | None = None
    retrieval_trace: RetrievalTrace | None = None
    pending_geography_clarification: PendingGeographyClarification | None = None
    requires_clarification: bool = False
    workflow_cancelled: bool = False

    def benchmark_is_not_applicable(self) -> bool:
        return isinstance(self.benchmark, BenchmarkNotApplicable)

    def resolved_temporal_intent(self) -> TemporalIntent | None:
        if isinstance(self.temporal, TemporalResolved):
            return self.temporal.time
        return None

    def resolved_geography_intent(self) -> GeographyIntent | None:
        from src.domain.geography_contract import GeographyResolved

        if isinstance(self.geography, GeographyResolved):
            return self.geography.geography
        return None

    def resolved_benchmark_intent(self) -> BenchmarkIntent | None:
        if isinstance(self.benchmark, BenchmarkResolved):
            return self.benchmark.benchmark
        return None
