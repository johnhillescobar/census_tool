"""Credentialed modern-runtime smoke tests (local keys required)."""

from __future__ import annotations

import os
import uuid

import pytest

from app import create_census_graph
from src.state.types import CensusState

QUERY = "What is the population of California in 2020?"

requires_credentials = pytest.mark.skipif(
    not os.getenv("CENSUS_API_KEY") or not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY and CENSUS_API_KEY",
)


def _state(question: str) -> CensusState:
    return CensusState(
        messages=[{"role": "user", "content": question}],
        original_query=question,
        intent={"is_census": True, "topic": "general"},
        plan=None,
        final=None,
        error=None,
        summary=None,
    )


@requires_credentials
@pytest.mark.integration
def test_modern_runtime_smoke_produces_answer(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)
    graph = create_census_graph()
    final_state = graph.invoke(
        _state(QUERY),
        config={
            "configurable": {
                "user_id": "runtime-smoke-modern",
                "thread_id": f"runtime-smoke-modern-{uuid.uuid4()}",
            }
        },
    )
    final = final_state.get("final") or {}
    assert final.get("answer_text"), "modern runtime returned empty answer"
