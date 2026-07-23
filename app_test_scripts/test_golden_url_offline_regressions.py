"""Offline geography-block regression for golden URL row 3 (no API keys)."""

from __future__ import annotations

import uuid

from app import create_census_graph
from app_test_scripts.census_url_fixtures import build_row_result, load_golden_questions
from src.services.graph_session import build_fresh_thread_state, runnable_config

ROW_3 = next(row for row in load_golden_questions() if row.row_no == 3)


def test_row3_geography_blocked_offline(record_census_urls, tier3_results_collector):
    """Documented P0: county+California friendly question hits geography gate with zero API calls."""
    graph = create_census_graph()
    config = runnable_config(user_id="golden-url-offline", thread_id=str(uuid.uuid4()))
    final_state = graph.invoke(build_fresh_thread_state(ROW_3.question), config=config)

    row_result = build_row_result(ROW_3, record_census_urls, final_state)
    tier3_results_collector.append(row_result)

    assert row_result.api_call_count == 0
    assert row_result.composite == "blocked"
    assert row_result.failure_class == "geography_blocked"
