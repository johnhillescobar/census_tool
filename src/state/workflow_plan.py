from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from src.domain.benchmark_contract import (
    BenchmarkIntent,
    BenchmarkResolution,
)
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import (
    TemporalIntent,
    TemporalResolution,
    TemporalResolved,
)
from src.domain.benchmark_contract import BenchmarkResolved


class BenchmarkNotApplicable(BaseModel):
    status: Literal["not_applicable"] = "not_applicable"
    reason: str


BenchmarkPlanState = Annotated[
    Union[BenchmarkResolution, BenchmarkNotApplicable],
    Field(discriminator="status"),
]


class WorkflowPlan(BaseModel):
    temporal: TemporalResolution | None = None
    benchmark: BenchmarkPlanState | None = None
    comparison: ComparisonPlan | None = None
    requires_clarification: bool = False

    def benchmark_is_not_applicable(self) -> bool:
        return isinstance(self.benchmark, BenchmarkNotApplicable)

    def resolved_temporal_intent(self) -> TemporalIntent | None:
        if isinstance(self.temporal, TemporalResolved):
            return self.temporal.time
        return None

    def resolved_benchmark_intent(self) -> BenchmarkIntent | None:
        if isinstance(self.benchmark, BenchmarkResolved):
            return self.benchmark.benchmark
        return None
