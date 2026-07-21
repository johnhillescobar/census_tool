"""Offline geography-block regression for golden URL row 3 (no API keys)."""

from __future__ import annotations

from app_test_scripts.census_url_fixtures import load_golden_questions
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.services.graph_session import build_fresh_thread_state
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node

ROW_3 = next(row for row in load_golden_questions() if row.row_no == 3)


def test_row3_geography_resolves_offline():
    state = build_fresh_thread_state(ROW_3.question)
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    fake = FakeGroundedRetrieval()
    result = geography_node(state, {}, dependencies=fake.dependencies())
    plan = result["plan"]
    geography = plan.resolved_geography_intent()
    assert plan.requires_clarification is False
    assert geography is not None
    assert geography.geo_for == {"county": "*"}
    assert geography.geo_in == {"state": "06"}
    assert geography.source == "chroma"
    assert plan.selected_table is not None
    assert any(item.collection_name == "census_tables" for item in plan.retrieval_evidence)
    assert ("geography", ("acs/acs5", 2023)) in fake.calls
