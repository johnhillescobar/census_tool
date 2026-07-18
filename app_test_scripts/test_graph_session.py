"""B2 graph session and turn-reset tests."""

from unittest.mock import MagicMock

import pytest

from src.services.graph_session import (
    build_delta_turn_state,
    build_fresh_thread_state,
    build_turn_state,
    build_turn_state_for_thread,
    resolve_thread_id,
    runnable_config,
    thread_has_checkpoint,
    turn_reset_artifacts,
)
from src.state.types import TURN_RESET_KEY, _artifacts_reducer


def test_turn_reset_artifacts_clears_merged_channel():
    existing = {"census_data": {"success": True, "data": [["Year", "Value"]]}}
    reset = turn_reset_artifacts()
    assert reset[TURN_RESET_KEY] is True
    cleared = _artifacts_reducer(existing, reset)
    assert cleared == {}


def test_delta_turn_state_resets_ephemeral_fields():
    state = build_delta_turn_state("follow up question")
    assert state.messages == [{"role": "user", "content": "follow up question"}]
    assert state.plan is None
    assert state.final is None
    assert state.geo is None
    assert state.error is None
    assert TURN_RESET_KEY in state.artifacts


def test_fresh_thread_state_includes_memory_channels():
    state = build_fresh_thread_state("hello")
    assert state.profile == {}
    assert state.history == []
    assert state.cache_index == {}
    assert state.artifacts == {}


def test_build_turn_state_selects_fresh_or_delta():
    fresh = build_turn_state("first", is_first_turn=True)
    delta = build_turn_state("second", is_first_turn=False)
    assert fresh.profile == {}
    assert TURN_RESET_KEY in delta.artifacts
    assert delta.plan is None


def test_resolve_thread_id_forces_new_thread():
    provided = "00000000-0000-0000-0000-000000000001"
    resolved = resolve_thread_id(thread_id=provided, new_thread=True)
    assert resolved != provided


@pytest.mark.parametrize("blank_thread_id", ["", "   "])
def test_resolve_thread_id_generates_uuid_for_blank_thread_id(blank_thread_id):
    resolved = resolve_thread_id(thread_id=blank_thread_id, new_thread=False)
    assert resolved
    assert resolved != blank_thread_id


def test_thread_has_checkpoint_uses_graph_messages():
    graph = MagicMock()
    config = runnable_config(user_id="demo", thread_id="thread-a")
    graph.get_state.return_value = MagicMock(values={})
    assert thread_has_checkpoint(graph, config) is False

    graph.get_state.return_value = MagicMock(values={"messages": [{"role": "user", "content": "hello"}]})
    assert thread_has_checkpoint(graph, config) is True


def test_build_turn_state_for_thread_uses_checkpoint_not_session_counter():
    graph = MagicMock()
    config = runnable_config(user_id="demo", thread_id="thread-a")
    graph.get_state.return_value = MagicMock(values={"messages": [{"role": "user", "content": "prior turn"}]})

    state = build_turn_state_for_thread(graph, "resume question", config=config)
    assert TURN_RESET_KEY in state.artifacts
    assert state.plan is None
