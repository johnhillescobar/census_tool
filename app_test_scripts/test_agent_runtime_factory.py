"""Runtime selection and backend factory tests."""

import pytest

from src.agents.runtime.factory import build_agent_backend, resolve_agent_runtime

pytestmark = pytest.mark.modern_runtime


def test_resolve_agent_runtime_defaults_modern(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)
    assert resolve_agent_runtime() == "modern"


def test_resolve_agent_runtime_rejects_unknown(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME", "invalid")
    with pytest.raises(ValueError):
        resolve_agent_runtime()


def test_build_modern_backend_without_llm_raises(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME", "modern")
    with pytest.raises(RuntimeError):
        build_agent_backend(
            runtime="modern",
            agent_executor=None,
            llm=None,
            tools=[],
            system_prompt="test",
        )


def test_build_agent_backend_rejects_unknown_runtime():
    with pytest.raises(ValueError, match="Unknown runtime"):
        build_agent_backend(
            runtime="invalid",
            agent_executor=None,
            llm=None,
            tools=[],
            system_prompt="test",
        )
