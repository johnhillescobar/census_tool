"""B2 durable SQLite checkpoint and thread isolation tests."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app import create_census_graph
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.domain.comparison_artifacts import ComparisonInputRow
from src.services.graph_session import (
    build_delta_turn_state,
    build_fresh_thread_state,
    build_turn_state_for_thread,
    runnable_config,
)
from src.state.types import TURN_RESET_KEY

_TURN1_STUB = {
    "answer_text": "Turn one answer from the stubbed agent.",
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
    "answer_text": "Turn two answer from the stubbed agent.",
    "census_data": {"success": True, "data": [["year", "value"], [2021, 200]]},
    "data_summary": "Turn two summary.",
    "reasoning_trace": "turn2",
    "charts_needed": [],
    "tables_needed": [],
    "footnotes": [],
    "comparison_input_rows": [],
}


def _grounded_config(thread_id: str, grounded):
    config = runnable_config(user_id="checkpoint-test", thread_id=thread_id)
    config["configurable"]["grounded_geography_dependencies"] = grounded
    return config


def _stub_agent(mock_agent_cls, *, turn1_stub=_TURN1_STUB, turn2_stub=_TURN2_STUB):
    mock_agent_cls.return_value.offline_mode = True
    mock_agent_cls.return_value.solve.return_value = turn1_stub
    return mock_agent_cls


@contextmanager
def _patched_agents(*, turn1_stub=_TURN1_STUB, turn2_stub=_TURN2_STUB):
    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls, patch(
        "src.workflows.agent_planning.CensusQueryAgent", mock_agent_cls
    ):
        _stub_agent(mock_agent_cls, turn1_stub=turn1_stub, turn2_stub=turn2_stub)
        yield mock_agent_cls


@pytest.fixture
def checkpoint_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("CENSUS_CHECKPOINT_DB", str(db_path))
    monkeypatch.delenv("CENSUS_RESET_CHECKPOINTS", raising=False)
    return db_path, FakeGroundedRetrieval().dependencies()


def test_checkpoint_survives_graph_recreation(checkpoint_db):
    _db_path, grounded = checkpoint_db
    thread_id = str(uuid.uuid4())
    config = _grounded_config(thread_id, grounded)

    with _patched_agents() as mock_agent_cls:
        graph1 = create_census_graph()
        graph1.invoke(build_fresh_thread_state("first county population in California question"), config)

        mock_agent_cls.return_value.solve.return_value = _TURN2_STUB
        graph2 = create_census_graph()
        final_state = graph2.invoke(build_delta_turn_state("second county population in California question"), config)

    assert len(final_state["messages"]) == 2
    assert final_state["messages"][0]["content"] == "first county population in California question"
    assert final_state["messages"][1]["content"] == "second county population in California question"


def test_different_threads_are_isolated(checkpoint_db):
    _db_path, grounded = checkpoint_db
    thread_a = str(uuid.uuid4())
    thread_b = str(uuid.uuid4())

    with _patched_agents():
        graph = create_census_graph()
        graph.invoke(
            build_fresh_thread_state("thread A county population in California question"),
            _grounded_config(thread_a, grounded),
        )
        final_b = graph.invoke(
            build_fresh_thread_state("thread B county population in California question"),
            _grounded_config(thread_b, grounded),
        )

    assert len(final_b["messages"]) == 1
    assert final_b["messages"][0]["content"] == "thread B county population in California question"


def test_delta_turn_clears_stale_artifacts(checkpoint_db):
    _db_path, grounded = checkpoint_db
    thread_id = str(uuid.uuid4())
    config = _grounded_config(thread_id, grounded)

    with _patched_agents() as mock_agent_cls:
        graph = create_census_graph()
        turn1 = graph.invoke(build_fresh_thread_state("first county population in California question"), config)
        assert turn1.get("artifacts", {}).get("comparison_input_rows")

        mock_agent_cls.return_value.solve.return_value = _TURN2_STUB
        final_state = graph.invoke(build_delta_turn_state("second county population in California question"), config)

    assert not final_state["artifacts"].get("comparison_input_rows")


def test_delta_turn_replaces_stale_final_answer(checkpoint_db):
    _db_path, grounded = checkpoint_db
    thread_id = str(uuid.uuid4())
    config = _grounded_config(thread_id, grounded)

    with _patched_agents() as mock_agent_cls:
        graph = create_census_graph()
        turn1 = graph.invoke(build_fresh_thread_state("first county population in California question"), config)
        assert turn1.get("final", {}).get("answer_text") == "Turn one answer from the stubbed agent."

        mock_agent_cls.return_value.solve.return_value = _TURN2_STUB
        final_state = graph.invoke(build_delta_turn_state("second county population in California question"), config)

    assert final_state.get("final", {}).get("answer_text") == "Turn two answer from the stubbed agent."


def test_new_conversation_thread_starts_fresh(checkpoint_db):
    _db_path, grounded = checkpoint_db
    thread_id = str(uuid.uuid4())

    with _patched_agents():
        graph = create_census_graph()
        graph.invoke(
            build_fresh_thread_state("old county population in California conversation"),
            _grounded_config(thread_id, grounded),
        )

        new_thread = str(uuid.uuid4())
        final_state = graph.invoke(
            build_fresh_thread_state("new county population in California conversation"),
            _grounded_config(new_thread, grounded),
        )

    assert len(final_state["messages"]) == 1
    assert final_state["messages"][0]["content"] == "new county population in California conversation"


def test_resumed_thread_id_uses_delta_turn_state(checkpoint_db):
    _db_path, grounded = checkpoint_db
    thread_id = str(uuid.uuid4())
    config = _grounded_config(thread_id, grounded)

    with _patched_agents():
        graph = create_census_graph()
        graph.invoke(build_fresh_thread_state("first county population in California question"), config)

        resumed_state = build_turn_state_for_thread(
            graph,
            "second county population in California question",
            config=config,
        )

    assert TURN_RESET_KEY in resumed_state.artifacts
    assert resumed_state.plan is None
