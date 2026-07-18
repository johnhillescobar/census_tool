"""Thread/session helpers for durable LangGraph checkpoint invokes."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.state.types import TURN_RESET_KEY, CensusState


def new_thread_id() -> str:
    """Create a durable conversation thread identifier."""
    return str(uuid.uuid4())


def runnable_config(*, user_id: str, thread_id: str) -> RunnableConfig:
    return RunnableConfig(configurable={"user_id": user_id, "thread_id": thread_id})


def turn_reset_artifacts() -> dict[str, Any]:
    """Marker payload that clears merged artifact channels at turn boundary."""
    return {TURN_RESET_KEY: True}


def build_delta_turn_state(user_message: str) -> CensusState:
    """Checkpoint continuation: one new user message plus ephemeral turn reset."""
    return CensusState(
        messages=[{"role": "user", "content": user_message}],
        original_query=user_message,
        intent=None,
        geo=None,
        candidates={},
        plan=None,
        artifacts=turn_reset_artifacts(),
        final=None,
        error=None,
        summary=None,
        logs=[],
    )


def build_fresh_thread_state(user_message: str) -> CensusState:
    """First turn on a new thread_id (no checkpoint history yet)."""
    return CensusState(
        messages=[{"role": "user", "content": user_message}],
        original_query=user_message,
        intent=None,
        geo=None,
        candidates={},
        plan=None,
        artifacts={},
        final=None,
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
        logs=[],
    )


def build_turn_state(user_message: str, *, is_first_turn: bool) -> CensusState:
    """Select fresh-thread or delta-turn input for a checkpointed invoke."""
    if is_first_turn:
        return build_fresh_thread_state(user_message)
    return build_delta_turn_state(user_message)


def thread_has_checkpoint(graph: Any, config: RunnableConfig) -> bool:
    """Return True when thread_id already has persisted graph messages."""
    try:
        snapshot = graph.get_state(config)
    except Exception:
        return False
    if snapshot is None:
        return False
    values = snapshot.values or {}
    messages = values.get("messages") or []
    return bool(messages)


def resolve_thread_id(*, thread_id: str | None, new_thread: bool) -> str:
    """Choose the checkpoint key for this request."""
    if new_thread:
        return new_thread_id()
    if thread_id is None:
        return new_thread_id()
    return thread_id


def build_turn_state_for_thread(
    graph: Any,
    user_message: str,
    *,
    config: RunnableConfig,
) -> CensusState:
    """Build invoke input from checkpoint history, not local session counters."""
    is_first_turn = not thread_has_checkpoint(graph, config)
    return build_turn_state(user_message, is_first_turn=is_first_turn)
