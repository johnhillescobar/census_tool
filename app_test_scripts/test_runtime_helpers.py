"""Shared helpers for runtime modernization tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.runtime.contracts import AgentExecutionResult


def mock_agent_backend(agent, mock_result: dict) -> MagicMock:
    backend = MagicMock()
    backend.invoke.return_value = AgentExecutionResult(
        output=str(mock_result.get("output", "")),
        intermediate_steps=list(mock_result.get("intermediate_steps") or []),
    )
    agent.backend = backend
    return backend
