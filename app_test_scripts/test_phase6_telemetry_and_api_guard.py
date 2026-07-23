"""Phase 6 telemetry envelope and grounded API guard acceptance tests."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime

import pytest

from app_test_scripts.census_url_fixtures import load_golden_questions
from app_test_scripts.golden_grounded_replay import build_golden_replay
from src.clients import telemetry
from src.services.grounded_census_planner import select_grounded_plan
from src.services.grounded_execution_context import (
    GroundedExecutionContext,
    reset_grounded_execution_context,
    set_grounded_execution_context,
    validate_grounded_api_request,
)
from src.services.grounded_plan_validator import validate_grounded_plan
from src.tools.strict_census_api_tool import StrictCensusApiTool


def _row3_replay():
    row = next(row for row in load_golden_questions() if row.row_no == 3)
    replay = build_golden_replay(row)
    assert replay is not None and replay.validation.plan is not None
    return replay


def test_telemetry_event_schema_is_json_stable_and_rejects_reserved_overrides():
    event = telemetry.build_event(
        "grounded_retrieval",
        {
            "trace_id": "phase6-trace",
            "stage": "plan_validation",
            "status": "resolved",
            "candidate_ids": ["golden:hierarchy:3"],
            "selected_ids": ["golden:hierarchy:3"],
        },
    )
    restored = telemetry.TelemetryEvent.model_validate_json(json.dumps(event))
    assert restored.event_type == "grounded_retrieval"
    assert restored.timestamp.tzinfo is not None
    assert datetime.fromisoformat(event["timestamp"]) == restored.timestamp
    assert event["candidate_ids"] == event["selected_ids"]

    with pytest.raises(ValueError, match="reserved fields"):
        telemetry.build_event("grounded_retrieval", {"event_type": "spoofed"})


def test_release_metrics_report_every_phase6_guard_signal():
    events = [
        {
            "event_type": "grounded_retrieval",
            "stage": "table_retrieval",
            "status": "hit",
            "candidate_ids": ["table:1"],
            "selected_ids": ["table:1"],
        },
        {
            "event_type": "grounded_retrieval",
            "stage": "plan_validation",
            "status": "rejected",
            "reason_code": "UNKNOWN_CANDIDATE_ID",
        },
        {
            "event_type": "grounded_plan",
            "geo_for": {"us": "1"},
            "explicit_geography": False,
        },
        {
            "event_type": "grounded_retrieval",
            "stage": "geography_retrieval",
            "status": "stale",
            "collection": "census_dataset_geographies",
        },
    ]
    rows = [{"failure_class": "geography_blocked"}, {"failure_class": "none"}]
    assert telemetry.release_metrics(events, rows) == {
        "table_search_events": 1,
        "geography_blocked": 1,
        "invented_ids": 1,
        "implicit_us": 1,
        "silent_chroma_miss": 1,
    }


@pytest.mark.parametrize("status", ["unavailable", "stale", "schema_mismatch"])
def test_validator_rejects_missing_or_stale_index_evidence(status):
    replay = _row3_replay()
    selection = select_grounded_plan(replay.table_evidence, replay.geography_evidence)
    evidence = deepcopy(replay.evidence)
    evidence[0] = evidence[0].model_copy(update={"status": status, "candidate_ids": [], "candidates": []})
    rejected = validate_grounded_plan(selection, evidence)
    assert rejected.status == "invalid"
    assert rejected.failures[0].reason_code == "EVIDENCE_NOT_USABLE"


def test_api_guard_accepts_exact_replay_and_rejects_geography_drift():
    replay = _row3_replay()
    plan = replay.validation.plan
    token = set_grounded_execution_context(GroundedExecutionContext(plan=plan, allowed_years=[2023]))
    try:
        accepted = validate_grounded_api_request(
            dataset=plan.table.dataset,
            year=2023,
            variables=["NAME", "B01001_001E"],
            geo_for=plan.geography.geo_for,
            geo_in=dict(plan.geography.geo_in),
        )
        rejected = validate_grounded_api_request(
            dataset=plan.table.dataset,
            year=2023,
            variables=["NAME", "B01001_001E"],
            geo_for={"county": "*"},
            geo_in={"state": "99"},
        )
    finally:
        reset_grounded_execution_context(token)

    assert accepted is None
    assert rejected == "Geography values are outside the validated plan"


def test_strict_api_guard_emits_schema_guard_event_and_never_fetches(monkeypatch):
    replay = _row3_replay()
    plan = replay.validation.plan
    events: list[tuple[str, dict]] = []

    def fail_fetch(**_kwargs):
        raise AssertionError("grounded guard rejection must happen before network access")

    monkeypatch.setattr("src.tools.strict_census_api_tool.fetch_census_data_typed", fail_fetch)
    monkeypatch.setattr(
        "src.tools.strict_census_api_tool.record_event",
        lambda event_type, payload: events.append((event_type, payload)),
    )
    token = set_grounded_execution_context(GroundedExecutionContext(plan=plan, allowed_years=[2023]))
    try:
        response = StrictCensusApiTool()._run(
            {
                "year": 2023,
                "dataset": plan.table.dataset,
                "variables": ["NAME", "B01001_001E"],
                "geo_for": {"county": "*"},
                "geo_in": {"state": "99"},
            }
        )
    finally:
        reset_grounded_execution_context(token)

    assert response.success is False
    assert response.error == "GROUNDED_PLAN_GUARD_REJECTED"
    guard_event = next(payload for event_type, payload in events if event_type == "grounded_api_guard")
    assert guard_event == {
        "tool": "strict_census_api_call",
        "success": False,
        "error": "Geography values are outside the validated plan",
    }
