from langchain_core.runnables import RunnableConfig

from src.domain.comparison_metric_contract import (
    ComparisonInputRow,
    ComparisonMetricComputeRequest,
)
from src.services.comparison_metric_compute import compute_comparison_metrics
from src.state.types import CensusState, WorkflowArtifactsState
from src.workflows.graph_patch import CensusGraphPatch


def _extract_comparison_rows(state: CensusState) -> list[ComparisonInputRow]:
    """
    Expected wired input contract from upstream tools/agent: typed
    `ComparisonInputRow` objects in `state.artifacts.comparison_input_rows`.
    """
    raw_rows = state.artifacts.comparison_input_rows if state.artifacts else []
    rows: list[ComparisonInputRow] = []
    for row in raw_rows:
        rows.append(ComparisonInputRow.model_validate(row))
    return rows


def comparison_metrics_node(
    state: CensusState, config: RunnableConfig
) -> dict[str, object]:
    plan_obj = state.plan
    if plan_obj and plan_obj.requires_clarification:
        return CensusGraphPatch(
            logs=["comparison_metrics: skipped (clarification required)"],
        ).as_langgraph_update()

    comparison_plan = plan_obj.comparison if plan_obj else None
    if not comparison_plan:
        return CensusGraphPatch(
            logs=["comparison_metrics: skipped (no comparison plan)"],
        ).as_langgraph_update()

    try:
        rows = _extract_comparison_rows(state)
    except Exception as exc:
        return CensusGraphPatch(
            logs=["comparison_metrics: failed (invalid comparison rows)"],
            error=f"comparison_metrics invalid rows: {exc}",
        ).as_langgraph_update()

    if not rows:
        return CensusGraphPatch(
            logs=["comparison_metrics: skipped (no comparison input rows)"],
        ).as_langgraph_update()

    request = ComparisonMetricComputeRequest(plan=comparison_plan, rows=rows)
    metric_rows = compute_comparison_metrics(request)

    return CensusGraphPatch(
        artifacts=WorkflowArtifactsState(comparison_metrics=metric_rows),
        logs=[f"comparison_metrics: computed {len(metric_rows)} rows"],
    ).as_langgraph_update()
