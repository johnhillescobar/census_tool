from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.comparison_artifacts import ComparisonInputRow
from src.domain.comparison_plan import ComparisonPlan


class WorkflowPipelineStage(StrEnum):
    TEMPORAL = "temporal"
    BENCHMARK = "benchmark"
    COMPARISON = "comparison"
    COMPARISON_METRICS = "comparison_metrics"


class WorkflowAcceptanceExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requires_clarification: bool
    stop_after: WorkflowPipelineStage
    temporal_status: Literal["resolved", "clarification_required"] | None = None
    benchmark_status: (
        Literal["resolved", "clarification_required", "not_applicable"] | None
    ) = None
    comparison_present: bool = False
    comparison_metrics_computed: bool = False
    expected_log_substrings: list[str] = Field(default_factory=list)
    benchmark_type: str | None = None
    temporal_mode: str | None = None
    reason_code: str | None = None

    @model_validator(mode="after")
    def validate_stage_expectations(self) -> "WorkflowAcceptanceExpectation":
        if self.stop_after == WorkflowPipelineStage.TEMPORAL:
            if self.temporal_status is None:
                raise ValueError("temporal_status is required when stop_after is temporal")
        if self.stop_after in {
            WorkflowPipelineStage.BENCHMARK,
            WorkflowPipelineStage.COMPARISON,
            WorkflowPipelineStage.COMPARISON_METRICS,
        }:
            if self.temporal_status != "resolved":
                raise ValueError(
                    "temporal_status must be resolved when pipeline continues past temporal"
                )
        if self.comparison_metrics_computed and not self.comparison_present:
            raise ValueError(
                "comparison_present must be True when comparison_metrics_computed is True"
            )
        return self


class WorkflowAcceptancePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    expectation: WorkflowAcceptanceExpectation
    comparison_input_rows: list[ComparisonInputRow] | None = None

    @model_validator(mode="after")
    def validate_metrics_inputs(self) -> "WorkflowAcceptancePlan":
        if self.expectation.comparison_metrics_computed and not self.comparison_input_rows:
            raise ValueError(
                "comparison_input_rows are required when comparison_metrics_computed is expected"
            )
        return self


class WorkflowAcceptanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    executed_stages: list[WorkflowPipelineStage]
    requires_clarification: bool
    temporal_status: str | None = None
    benchmark_status: str | None = None
    comparison_plan: ComparisonPlan | None = None
    comparison_metrics_count: int = 0
    logs: list[str] = Field(default_factory=list)
    final_answer_present: bool = False
