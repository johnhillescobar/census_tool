import json
from unittest.mock import MagicMock

import pytest

from src.agents.census_query_agent import CensusQueryAgent
from src.state.types import CensusState
from src.workflows.output import is_census_data_renderable, output_node


@pytest.fixture
def offline_agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = CensusQueryAgent(allow_offline=False)
    agent.agent_executor = MagicMock()
    return agent


def test_clarification_answer_is_not_overwritten(offline_agent):
    clarification = (
        "Which geography do you want for the median household income trend from 2015–2020?"
    )
    mock_result = {
        "output": json.dumps(
            {
                "census_data": {"success": False, "data": []},
                "data_summary": "Missing geography",
                "reasoning_trace": "Stopped before API calls",
                "answer_text": clarification,
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [],
            }
        ),
        "intermediate_steps": [],
    }
    offline_agent.agent_executor.invoke.return_value = mock_result
    result = offline_agent.solve(
        "Show me median income trends from 2015 to 2020",
        {"is_census": True, "topic": "general"},
    )
    assert clarification in result["answer_text"]
    assert "unable to complete this query" not in result["answer_text"].lower()


def test_invalid_geography_still_normalizes(offline_agent):
    mock_result = {
        "output": json.dumps(
            {
                "census_data": {"success": False, "data": []},
                "data_summary": "Invalid geography",
                "reasoning_trace": "resolve_area_name failed",
                "answer_text": "Mars has no census data",
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [],
            }
        ),
        "intermediate_steps": [
            (
                MagicMock(
                    tool="resolve_area_name",
                    tool_input='{"name":"Mars","geography_type":"state"}',
                ),
                "No match found for 'Mars' in state",
            )
        ],
    }
    offline_agent.agent_executor.invoke.return_value = mock_result
    result = offline_agent.solve(
        "What's the population of Mars?",
        {"is_census": True, "topic": "general"},
    )
    assert "unable to complete" in result["answer_text"].lower()


def test_renderability_guard_blocks_empty_success_false_payload():
    assert is_census_data_renderable({"success": False, "data": []}) is False
    assert is_census_data_renderable({"success": True, "data": []}) is False
    assert is_census_data_renderable(
        {"success": True, "data": [["Year", "Value"], ["2015", "100"]]}
    )


def test_output_node_skips_chart_on_failed_census_data():
    state = CensusState(
        messages=[{"role": "user", "content": "test"}],
        original_query="test",
        intent=None,
        plan=None,
        artifacts={"census_data": {"success": False, "data": []}},
        final={
            "answer_text": "Need more info",
            "charts_needed": [{"type": "line", "title": "Trend"}],
            "tables_needed": [],
            "footnotes": [],
        },
        error=None,
        summary=None,
    )
    result = output_node(state, {})
    assert result["final"]["generated_files"] == []
