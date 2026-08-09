"""CENSUS-43: planning turn uses table_catalog_retrieval, not table_search."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agents.census_query_agent import CensusQueryAgent
from src.llm.prompts.planning_agent import build_planning_agent_prompt


def test_planning_mode_excludes_table_search(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("src.agents.census_query_agent.create_llm", return_value=MagicMock()):
        with patch("src.agents.census_query_agent.build_agent_backend", return_value=MagicMock()):
            agent = CensusQueryAgent(allow_offline=False, mode="planning")

    tool_names = {tool.name for tool in agent.tools}
    assert "table_search" not in tool_names


def test_planning_mode_includes_table_catalog_retrieval(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("src.agents.census_query_agent.create_llm", return_value=MagicMock()):
        with patch("src.agents.census_query_agent.build_agent_backend", return_value=MagicMock()):
            agent = CensusQueryAgent(allow_offline=False, mode="planning")

    tool_names = {tool.name for tool in agent.tools}
    assert "table_catalog_retrieval" in tool_names


def test_planning_prompt_directs_catalog_retrieval_not_table_search():
    prompt = build_planning_agent_prompt(
        [
            "table_catalog_retrieval",
            "geography_discovery",
            "propose_grounded_plan",
            "select_clarification_option",
        ]
    )
    lowered = prompt.lower()
    assert "table_catalog_retrieval" in lowered
    assert "do not use table_search" in lowered
    assert "dataset" in lowered and "year" in lowered
