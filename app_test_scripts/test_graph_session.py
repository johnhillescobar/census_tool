"""B2 graph session and turn-reset tests."""

from src.services.graph_session import (
    build_delta_turn_state,
    build_fresh_thread_state,
    build_turn_state,
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
