"""Validate agent outputs against deterministic planning obligations."""

from __future__ import annotations

from typing import Any

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.execution_spec import build_execution_spec


def _strip_presentation(result: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(result)
    cleaned["charts_needed"] = []
    cleaned["tables_needed"] = []
    return cleaned


def validate_agent_result_against_plan(
    result: dict[str, Any],
    plan_context: AgentPlanContext | None,
) -> dict[str, Any]:
    """Apply post-agent plan enforcement without inventing census data."""
    if plan_context is None:
        return result

    spec = build_execution_spec(plan_context)
    if spec is None:
        return result

    census_data = result.get("census_data") or {}
    success = isinstance(census_data, dict) and census_data.get("success") is True
    answer_text = (result.get("answer_text") or "").strip()

    if not success:
        # Clarification/failure must not request presentation artifacts.
        if result.get("charts_needed") or result.get("tables_needed"):
            return _strip_presentation(result)
        return result

    if spec.requires_time_series and spec.query_years:
        data_rows = census_data.get("data") or []
        if not isinstance(data_rows, list) or len(data_rows) < 2:
            return {
                **result,
                "census_data": {"success": False, "data": []},
                "data_summary": "Plan validation failed: expected time-series rows",
                "answer_text": (
                    "I could not assemble the requested year-by-year series for "
                    f"{spec.geography.display_name} ({spec.temporal.start_year}–"
                    f"{spec.temporal.end_year})."
                ),
                "charts_needed": [],
                "tables_needed": [],
            }

        year_column = str(data_rows[0][0]).lower() if data_rows[0] else ""
        if "year" not in year_column:
            return {
                **result,
                "data_summary": result.get("data_summary", "")
                + " [plan note: missing Year column in series output]",
            }

    if not answer_text:
        result["answer_text"] = (
            f"Results for {spec.geography.display_name} using the resolved planning constraints."
        )

    return result
