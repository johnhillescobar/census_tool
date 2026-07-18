from typing import Any

from langchain_core.runnables import RunnableConfig

from src.domain.comparison_artifacts import (
    ComparisonInputRow,
    ComparisonMetricArtifactRow,
    ComparisonMetricsArtifact,
)
from src.services.comparison_metric_compute import (
    ComparisonMetricComputeRequest,
    compute_comparison_metrics,
)
from src.state.types import CensusState, WorkflowArtifactsState
from src.workflows.graph_patch import CensusGraphPatch


def _extract_comparison_rows(state: CensusState) -> list[ComparisonInputRow]:
    """
    Expected wired input contract from upstream tools/agent:
      state.artifacts["comparison_input_rows"] = [
        {"year": 2020, "geo_id": "10001", "metric": "population", "value": 10.0, "benchmark_value": 8.0},
        ...
      ]
    """
    raw_rows = (state.artifacts or {}).get("comparison_input_rows", [])
    rows: list[ComparisonInputRow] = []
    for row in raw_rows:
        rows.append(ComparisonInputRow.model_validate(row))
    return rows


def comparison_metrics_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    plan = state.plan
    if plan is None or plan.requires_clarification:
        return {
            "logs": ["comparison_metrics: skipped (clarification required)"],
        }

    comparison_plan = plan.comparison
    if comparison_plan is None:
        return {
            "logs": ["comparison_metrics: skipped (no comparison plan)"],
        }

    try:
        rows = _extract_comparison_rows(state)
    except Exception as exc:
        return {
            "logs": ["comparison_metrics: failed (invalid comparison rows)"],
            "error": f"comparison_metrics invalid rows: {exc}",
        }

    if not rows:
        return {
            "logs": ["comparison_metrics: skipped (no comparison input rows)"],
        }

    request = ComparisonMetricComputeRequest(plan=comparison_plan, rows=rows)
    metric_rows = compute_comparison_metrics(request)
    metrics_artifact = ComparisonMetricsArtifact(
        rows=[ComparisonMetricArtifactRow.model_validate(row.model_dump()) for row in metric_rows]
    )

    return CensusGraphPatch(
        artifacts=WorkflowArtifactsState(comparison_metrics=metrics_artifact.rows),
        logs=[f"comparison_metrics: computed {len(metrics_artifact.rows)} rows"],
    ).as_langgraph_update()
