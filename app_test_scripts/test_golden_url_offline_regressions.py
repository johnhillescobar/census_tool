"""Offline geography-block regression for golden URL row 3 (no API keys)."""

from __future__ import annotations

import uuid

import pytest

from app import create_census_graph
from app_test_scripts.census_url_fixtures import load_golden_questions
from src.services.graph_session import build_fresh_thread_state, runnable_config

ROW_3 = next(row for row in load_golden_questions() if row.row_no == 3)


@pytest.mark.xfail(
    strict=True,
    reason="P0 target: Chroma-grounded planning must compose county:* within state:06",
)
def test_row3_geography_resolves_offline():
    graph = create_census_graph()
    config = runnable_config(user_id="golden-url-offline", thread_id=str(uuid.uuid4()))
    final_state = graph.invoke(build_fresh_thread_state(ROW_3.question), config=config)

    plan = final_state["plan"]
    geography = plan.resolved_geography_intent()
    assert plan.requires_clarification is False
    assert geography is not None
    assert geography.geo_for == {"county": "*"}
    assert geography.geo_in == {"state": "06"}
