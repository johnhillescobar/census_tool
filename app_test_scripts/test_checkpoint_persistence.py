"""B2 durable SQLite checkpoint and thread isolation tests."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app import create_census_graph
from src.domain.comparison_artifacts import ComparisonInputRow
from src.services.graph_session import (
    build_delta_turn_state,
    build_fresh_thread_state,
    runnable_config,
)

_TURN1_STUB = {
    "answer_text": "Turn one answer.",
    "census_data": {
        "success": True,
        "data": [["year", "value"], [2020, 100]],
    },
    "data_summary": "Turn one summary.",
    "reasoning_trace": "turn1",
    "charts_needed": [],
    "tables_needed": [],
    "footnotes": [],
    "comparison_input_rows": [
        ComparisonInputRow(
            year=2020,
            geo_id="06001",
            metric="population",
            value=100.0,
            benchmark_value=90.0,
        )
    ],
}

_TURN2_STUB = {
    "answer_text": "Turn two answer.",
    "census_data": {"success": True, "data": [["year", "value"], [2021, 200]]},
    "data_summary": "Turn two summary.",
    "reasoning_trace": "turn2",
    "charts_needed": [],
    "tables_needed": [],
    "footnotes": [],
    "comparison_input_rows": [],
}


@pytest.fixture
def checkpoint_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("CENSUS_CHECKPOINT_DB", str(db_path))
    monkeypatch.delenv("CENSUS_RESET_CHECKPOINTS", raising=False)
    return db_path


def test_checkpoint_survives_graph_recreation(checkpoint_db):
    thread_id = str(uuid.uuid4())
    config = runnable_config(user_id="checkpoint-test", thread_id=thread_id)

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = _TURN1_STUB
        graph1 = create_census_graph()
        graph1.invoke(build_fresh_thread_state("first question"), config)

        mock_agent_cls.return_value.solve.return_value = _TURN2_STUB
        graph2 = create_census_graph()
        final_state = graph2.invoke(build_delta_turn_state("second question"), config)

    assert len(final_state["messages"]) == 2
    assert final_state["messages"][0]["content"] == "first question"
    assert final_state["messages"][1]["content"] == "second question"


def test_different_threads_are_isolated(checkpoint_db):
    thread_a = str(uuid.uuid4())
    thread_b = str(uuid.uuid4())

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = _TURN1_STUB
        graph = create_census_graph()
        graph.invoke(
            build_fresh_thread_state("thread A question"),
            runnable_config(user_id="checkpoint-test", thread_id=thread_a),
        )
        final_b = graph.invoke(
            build_fresh_thread_state("thread B question"),
            runnable_config(user_id="checkpoint-test", thread_id=thread_b),
        )

    assert len(final_b["messages"]) == 1
    assert final_b["messages"][0]["content"] == "thread B question"


def test_delta_turn_clears_stale_artifacts(checkpoint_db):
    thread_id = str(uuid.uuid4())
    config = runnable_config(user_id="checkpoint-test", thread_id=thread_id)

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = _TURN1_STUB
        graph = create_census_graph()
        turn1 = graph.invoke(build_fresh_thread_state("first question"), config)
        assert turn1.get("artifacts", {}).get("comparison_input_rows")

        mock_agent_cls.return_value.solve.return_value = _TURN2_STUB
        final_state = graph.invoke(build_delta_turn_state("second question"), config)

    assert not final_state["artifacts"].get("comparison_input_rows")


def test_new_conversation_thread_starts_fresh(checkpoint_db):
    thread_id = str(uuid.uuid4())

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = _TURN1_STUB
        graph = create_census_graph()
        graph.invoke(
            build_fresh_thread_state("old conversation"),
            runnable_config(user_id="checkpoint-test", thread_id=thread_id),
        )

        new_thread = str(uuid.uuid4())
        final_state = graph.invoke(
            build_fresh_thread_state("new conversation"),
            runnable_config(user_id="checkpoint-test", thread_id=new_thread),
        )

    assert len(final_state["messages"]) == 1
    assert final_state["messages"][0]["content"] == "new conversation"
