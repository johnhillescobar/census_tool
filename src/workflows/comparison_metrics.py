from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.domain.comparison_plan import ComparisonPlan
from src.services.comparison_metric_compute import (
    ComparisonInputRow,
    ComparisonMetricComputeRequest,
    compute_comparison_metrics,
)
from src.state.types import CensusState


class ComparisonMetricsNodeOutput(BaseModel):
    artifacts: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    error: str | None = None


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
    plan_obj = state.plan or {}
    if plan_obj.get("requires_clarification"):
        output = ComparisonMetricsNodeOutput(
            logs=["comparison_metrics: skipped (clarification required)"]
        )
        return output.model_dump(exclude_none=True)

    comparison_plan_raw = plan_obj.get("comparison")
    if not comparison_plan_raw:
        output = ComparisonMetricsNodeOutput(
            logs=["comparison_metrics: skipped (no comparison plan)"]
        )
        return output.model_dump(exclude_none=True)

    try:
        comparison_plan = ComparisonPlan.model_validate(comparison_plan_raw)
    except Exception as exc:  # keep workflow fail-closed
        output = ComparisonMetricsNodeOutput(
            logs=["comparison_metrics: failed (invalid comparison plan)"],
            error=f"comparison_metrics invalid plan: {exc}",
        )
        return output.model_dump(exclude_none=True)

    try:
        rows = _extract_comparison_rows(state)
    except Exception as exc:
        output = ComparisonMetricsNodeOutput(
            logs=["comparison_metrics: failed (invalid comparison rows)"],
            error=f"comparison_metrics invalid rows: {exc}",
        )
        return output.model_dump(exclude_none=True)

    if not rows:
        output = ComparisonMetricsNodeOutput(
            logs=["comparison_metrics: skipped (no comparison input rows)"]
        )
        return output.model_dump(exclude_none=True)

    request = ComparisonMetricComputeRequest(plan=comparison_plan, rows=rows)
    metric_rows = compute_comparison_metrics(request)

    output = ComparisonMetricsNodeOutput(
        artifacts={"comparison_metrics": [row.model_dump() for row in metric_rows]},
        logs=[f"comparison_metrics: computed {len(metric_rows)} rows"],
    )
    return output.model_dump(exclude_none=True)

