"""Phase 6 acceptance and deterministic model-drift coverage."""

from __future__ import annotations

import json

import pytest

from app_test_scripts.census_url_fixtures import load_golden_questions
from app_test_scripts.golden_grounded_replay import (
    build_golden_replay,
    canonical_geo_for,
    canonical_geo_in,
)
from src.domain.retrieval_plan import GroundedSelection
from src.services.grounded_plan_validator import validate_grounded_plan

GOLDEN_ROWS = load_golden_questions()
DATA_ROWS = [row for row in GOLDEN_ROWS if not row.is_catalog_url]
CATALOG_ROWS = [row for row in GOLDEN_ROWS if row.is_catalog_url]


def test_golden_replay_fixture_covers_122_data_rows_and_bypasses_two_catalog_rows():
    assert len(GOLDEN_ROWS) == 124
    assert len(DATA_ROWS) == 122
    assert [row.row_no for row in CATALOG_ROWS] == [9, 10]
    assert all(build_golden_replay(row) is None for row in CATALOG_ROWS)


@pytest.mark.parametrize("row", DATA_ROWS, ids=lambda row: f"row_{row.row_no}")
def test_all_golden_data_rows_replay_through_explicit_proposed_ids_and_validator(row):
    replay = build_golden_replay(row)
    assert replay is not None
    assert replay.table_evidence.collection_name == "census_tables"
    assert replay.table_evidence.status == "hit"
    assert replay.table_evidence.candidate_ids

    validation = replay.validation
    assert validation.status == "valid", validation.failures
    assert validation.plan is not None and validation.plan.geography is not None
    assert validation.plan.geography.geo_for == canonical_geo_for(row)
    assert validation.plan.geography.geo_in == canonical_geo_in(row)

    supplied_ids = {candidate_id for item in replay.evidence for candidate_id in item.candidate_ids}
    selected_ids = {
        validation.plan.table.candidate_id,
        validation.plan.geography.hierarchy_candidate_id,
        *validation.plan.geography.area_candidate_ids,
    }
    assert selected_ids <= supplied_ids

    expected_for = canonical_geo_for(row)
    if "us" in validation.plan.geography.geo_for:
        assert "us" in expected_for, f"row {row.row_no} invented a national default"


@pytest.mark.parametrize("row", DATA_ROWS, ids=lambda row: f"row_{row.row_no}")
def test_golden_replay_is_deterministic_for_model_drift_detection(row):
    first = build_golden_replay(row)
    second = build_golden_replay(row)
    assert first is not None and second is not None
    assert first.fingerprint() == second.fingerprint()
    assert first.validation.model_dump(mode="json") == second.validation.model_dump(mode="json")


def test_replay_validator_rejects_an_invented_candidate_id():
    replay = build_golden_replay(DATA_ROWS[0])
    assert replay is not None
    evidence_ids = [item.evidence_id for item in replay.evidence]
    invented = GroundedSelection(
        selection_id="phase6-invented-id-guard",
        status="selected",
        evidence_ids=evidence_ids,
        selected_table_ids=replay.table_evidence.candidate_ids,
        selected_hierarchy_id="candidate:not-in-retrieved-evidence",
    )
    rejected = validate_grounded_plan(invented, replay.evidence)
    assert rejected.status == "invalid"
    assert rejected.failures[0].reason_code == "UNKNOWN_CANDIDATE_ID"


def test_replay_fingerprint_detects_canonical_model_drift():
    replay = build_golden_replay(DATA_ROWS[2])
    assert replay is not None and replay.validation.plan is not None
    baseline = replay.fingerprint()
    replay.validation.plan.geography.geo_in[0] = ("state", "99")
    assert replay.fingerprint() != baseline
    assert json.dumps(replay.validation.model_dump(mode="json"), sort_keys=True)
