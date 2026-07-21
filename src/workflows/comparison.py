from typing import Any

from langchain_core.runnables import RunnableConfig

from src.domain.benchmark_contract import BenchmarkResolved
from src.domain.temporal_contract import TemporalResolved
from src.services.comparison_plan_policy import resolve_comparison_plan
from src.state.types import CensusState
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan


def comparison_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    existing_plan = state.plan
    if existing_plan is None:
        return {
            "plan": WorkflowPlan(requires_clarification=True),
            "logs": ["comparison: missing plan"],
        }

    temporal = existing_plan.temporal
    benchmark = existing_plan.benchmark

    if existing_plan.requires_clarification:
        return {
            "plan": existing_plan.model_copy(update={"requires_clarification": True}),
            "logs": ["comparison: skipped (clarification required)"],
        }

    if temporal is None or benchmark is None:
        return {
            "plan": existing_plan.model_copy(update={"requires_clarification": True}),
            "logs": ["comparison: missing temporal/benchmark plan"],
        }

    if isinstance(benchmark, BenchmarkNotApplicable):
        return {
            "plan": existing_plan.model_copy(update={"requires_clarification": False}),
            "logs": ["comparison: skipped (benchmark not applicable)"],
        }

    if not isinstance(temporal, TemporalResolved) or not isinstance(benchmark, BenchmarkResolved):
        return {
            "plan": existing_plan.model_copy(update={"requires_clarification": True}),
            "logs": ["comparison: upstream plan unresolved"],
        }

    comparison = resolve_comparison_plan(benchmark.benchmark, temporal.time)

    return {
        "plan": existing_plan.model_copy(update={"comparison": comparison, "requires_clarification": False}),
        "logs": ["comparison: resolved"],
    }
