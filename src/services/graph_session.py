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
