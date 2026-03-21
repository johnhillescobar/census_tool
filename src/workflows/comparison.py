from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.temporal_contract import TemporalIntent
from src.services.comparison_plan_policy import resolve_comparison_plan
from src.state.types import CensusState

class ComparisonWorkflowPlan(BaseModel):
    temporal: dict[str, Any] | None = None
    benchmark: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    requires_clarification: bool


class FinalPayload(BaseModel):
    answer_text: str
    charts_needed: list[dict[str, Any]] = Field(default_factory=list)
    tables_needed: list[dict[str, Any]] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)


class ComparisonNodeOutput(BaseModel):
    plan: ComparisonWorkflowPlan
    final: FinalPayload | None = None
    logs: list[str] = Field(default_factory=list)


def comparison_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    existing_plan = state.plan or {}
    temporal_plan = existing_plan.get("temporal")
    benchmark_plan = existing_plan.get("benchmark")

    if existing_plan.get("requires_clarification"):
        output = ComparisonNodeOutput(
            plan=ComparisonWorkflowPlan(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            logs=["comparison: skipped (clarification required)"],
        )
        return output.model_dump(exclude_none=True)

    if not temporal_plan or not benchmark_plan:
        output = ComparisonNodeOutput(
            plan=ComparisonWorkflowPlan(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            logs=["comparison: missing temporal/benchmark plan"],
        )
        return output.model_dump(exclude_none=True)

    if benchmark_plan.get("status") == "not_applicable":
        output = ComparisonNodeOutput(
            plan=ComparisonWorkflowPlan(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=False,
            ),
            logs=["comparison: skipped (benchmark not applicable)"],
        )
        return output.model_dump(exclude_none=True)

    if temporal_plan.get("status") != "resolved" or benchmark_plan.get("status") != "resolved":
        output = ComparisonNodeOutput(
            plan=ComparisonWorkflowPlan(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            logs=["comparison: upstream plan unresolved"],
        )
        return output.model_dump(exclude_none=True)

    temporal_intent = TemporalIntent.model_validate(temporal_plan.get("time", {}))
    benchmark_intent = BenchmarkIntent.model_validate(benchmark_plan.get("benchmark", {}))
    comparison = resolve_comparison_plan(benchmark_intent, temporal_intent)

    output = ComparisonNodeOutput(
        plan=ComparisonWorkflowPlan(
            temporal=temporal_plan,
            benchmark=benchmark_plan,
            comparison=comparison.model_dump(),
            requires_clarification=False,
        ),
        logs=["comparison: resolved"],
    )
    return output.model_dump(exclude_none=True)