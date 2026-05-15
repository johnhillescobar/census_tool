from langchain_core.runnables import RunnableConfig

from src.domain.benchmark_contract import BenchmarkResolved
from src.domain.temporal_contract import TemporalResolved
from src.services.comparison_plan_policy import resolve_comparison_plan
from src.state.types import CensusState, WorkflowPlanState
from src.workflows.graph_patch import CensusGraphPatch


def comparison_node(state: CensusState, config: RunnableConfig) -> dict[str, object]:
    existing_plan = state.plan
    temporal_plan = existing_plan.temporal if existing_plan else None
    benchmark_plan = existing_plan.benchmark if existing_plan else None

    if existing_plan and existing_plan.requires_clarification:
        return CensusGraphPatch(
            plan=WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            logs=["comparison: skipped (clarification required)"],
        ).as_langgraph_update()

    if not temporal_plan or not benchmark_plan:
        return CensusGraphPatch(
            plan=WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            logs=["comparison: missing temporal/benchmark plan"],
        ).as_langgraph_update()

    if benchmark_plan.status == "not_applicable":
        return CensusGraphPatch(
            plan=WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=False,
            ),
            logs=["comparison: skipped (benchmark not applicable)"],
        ).as_langgraph_update()

    if not isinstance(temporal_plan, TemporalResolved) or not isinstance(
        benchmark_plan, BenchmarkResolved
    ):
        return CensusGraphPatch(
            plan=WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_plan,
                comparison=None,
                requires_clarification=True,
            ),
            logs=["comparison: upstream plan unresolved"],
        ).as_langgraph_update()

    comparison = resolve_comparison_plan(benchmark_plan.benchmark, temporal_plan.time)

    return CensusGraphPatch(
        plan=WorkflowPlanState(
            temporal=temporal_plan,
            benchmark=benchmark_plan,
            comparison=comparison,
            requires_clarification=False,
        ),
        logs=["comparison: resolved"],
    ).as_langgraph_update()
