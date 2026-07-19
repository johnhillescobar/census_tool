"""Tier 3: natural-language E2E collection with URL capture and dual verdicts."""

from __future__ import annotations

import os
import uuid

import pytest

from app import create_census_graph
from app_test_scripts.census_url_fixtures import (
    build_row_result,
    golden_collect_mode,
    golden_strict_mode,
    load_golden_questions,
)
from src.services.graph_session import build_fresh_thread_state, runnable_config

requires_credentials = pytest.mark.skipif(
    not os.getenv("CENSUS_API_KEY") or not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY and CENSUS_API_KEY",
)

SMOKE_ROW_NOS = {1, 2, 3, 4, 5, 8, 11, 16, 19, 22, 9, 10}
SMOKE_ROWS = [row for row in load_golden_questions() if row.row_no in SMOKE_ROW_NOS]


@pytest.mark.integration
@pytest.mark.slow
@requires_credentials
@pytest.mark.parametrize("row", SMOKE_ROWS, ids=lambda r: f"row_{r.row_no}")
def test_nl_question_collect_url_and_delivery(row, record_census_urls, tier3_results_collector):
    if row.is_catalog_url:
        pytest.skip("Catalog queries may use a different agent tool path in Phase A")

    graph = create_census_graph()
    config = runnable_config(
        user_id="golden-url-e2e",
        thread_id=str(uuid.uuid4()),
    )
    final_state = graph.invoke(build_fresh_thread_state(row.question), config=config)

    row_result = build_row_result(row, record_census_urls, final_state)
    tier3_results_collector.append(row_result)

    if golden_collect_mode():
        return

    if golden_strict_mode():
        assert row_result.composite != "false_failure", row_result.to_dict()
        return

    # Default after baseline: only hard-fail false_failure (retries/extra calls allowed).
    assert row_result.composite != "false_failure", row_result.to_dict()
