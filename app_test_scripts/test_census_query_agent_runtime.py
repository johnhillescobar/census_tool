"""CensusQueryAgent runtime seam tests (A1)."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.census_query_agent import CensusQueryAgent
from src.agents.runtime.contracts import AgentExecutionResult


def test_census_query_agent_uses_modern_backend_when_credentials_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)
    with patch("src.agents.census_query_agent.create_llm") as mock_create_llm:
        mock_create_llm.return_value = MagicMock()
        with patch("src.agents.census_query_agent.build_agent_backend") as mock_build:
            mock_build.return_value = MagicMock()
            agent = CensusQueryAgent(allow_offline=False)
    mock_build.assert_called_once()
    assert agent.backend is mock_build.return_value
    assert agent.runtime == "modern"


def test_census_query_agent_rejects_classic_runtime_at_init(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_RUNTIME", "classic")
    with pytest.raises(ValueError, match="removed after A4 cutover"):
        CensusQueryAgent(allow_offline=False)


def test_census_query_agent_rejects_classic_runtime_in_offline_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_RUNTIME", "classic")
    with pytest.raises(ValueError, match="removed after A4 cutover"):
        CensusQueryAgent(allow_offline=True)


def test_census_query_agent_solve_delegates_to_backend(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = CensusQueryAgent(allow_offline=True)
    backend = MagicMock()
    backend.invoke.return_value = AgentExecutionResult(
        output='{"answer_text":"stub answer","census_data":{"success":true,"data":[]},'
        '"data_summary":"s","reasoning_trace":"r","charts_needed":[],"tables_needed":[],'
        '"footnotes":[],"comparison_input_rows":[]}',
        intermediate_steps=[],
    )
    agent.backend = backend
    parsed = agent.solve("population?", {"is_census": True})
    backend.invoke.assert_called_once()
    assert parsed["answer_text"] == "stub answer"
