from typing import Any

from langchain_core.runnables import RunnableConfig

from src.domain.benchmark_contract import BenchmarkResolved
from src.domain.temporal_contract import TemporalResolved
from src.services.comparison_plan_policy import resolve_comparison_plan
from src.state.types import CensusState, WorkflowPlanState


def comparison_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    existing_plan = state.plan
    temporal_plan = existing_plan.temporal if existing_plan else None
    benchmark_plan = existing_plan.benchmark if existing_plan else None

    if existing_plan and existing_plan.requires_clarification:
        return {
            "plan": WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            "logs": ["comparison: skipped (clarification required)"],
        }

    if not temporal_plan or not benchmark_plan:
        return {
            "plan": WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            "logs": ["comparison: missing temporal/benchmark plan"],
        }

    if benchmark_plan.status == "not_applicable":
        return {
            "plan": WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=False,
            ),
            "logs": ["comparison: skipped (benchmark not applicable)"],
        }

    if not isinstance(temporal_plan, TemporalResolved) or not isinstance(
        benchmark_plan, BenchmarkResolved
    ):
        return {
            "plan": WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            "logs": ["comparison: upstream plan unresolved"],
        }

    comparison = resolve_comparison_plan(benchmark_plan.benchmark, temporal_plan.time)

    return {
        "plan": WorkflowPlanState(
            temporal=temporal_plan,
            benchmark=benchmark_plan,
            comparison=comparison,
            requires_clarification=False,
        ),
        "logs": ["comparison: resolved"],
    }
