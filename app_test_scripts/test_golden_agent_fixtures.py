import json
from unittest.mock import MagicMock

import pytest

from app_test_scripts.test_runtime_helpers import mock_agent_backend
from src.agents.census_query_agent import CensusQueryAgent
from src.domain.agent_plan_context import AgentPlanContext
from src.domain.geography_contract import GeographyIntent
from src.domain.temporal_contract import TemporalIntent
from src.services.agent_plan_context import format_plan_directives


@pytest.fixture
def offline_agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = CensusQueryAgent(allow_offline=False)
    agent.agent_executor = MagicMock()
    agent.backend = MagicMock()
    return agent


def test_plan_directives_include_us_default_and_year_obligation():
    ctx = AgentPlanContext(
        geography=GeographyIntent(
            level="nation",
            geo_for={"us": "1"},
            geo_in={},
            display_name="United States",
            source="chroma",
        ),
        temporal=TemporalIntent(
            mode="range",
            start_year=2015,
            end_year=2020,
            anchor_year=None,
            missing_year_policy="skip_with_note",
            requested_text="Show me median income trends from 2015 to 2020",
        ),
        benchmark=None,
        comparison=None,
        has_comparison_plan=False,
    )
    directives = format_plan_directives(ctx)
    assert "geo_for: {'us': '1'}" in directives
    assert "Required query years: [2015, 2016, 2017, 2018, 2019, 2020]" in directives
    assert "Do NOT ask the user for geography again" in directives


def test_golden_success_payload_parses(offline_agent):
    payload = {
        "census_data": {
            "success": True,
            "data": [["Year", "Median Household Income"], ["2015", "55000"]],
        },
        "data_summary": "US median income",
        "reasoning_trace": "Queried ACS",
        "answer_text": "Median household income in 2015 was $55,000.",
        "charts_needed": [{"type": "line", "title": "Median income trend"}],
        "tables_needed": [],
        "footnotes": ["Source: U.S. Census Bureau"],
    }
    mock_agent_backend(
        offline_agent,
        {
            "output": json.dumps(payload),
            "intermediate_steps": [],
        },
    )
    result = offline_agent.solve("test", {"is_census": True, "topic": "general"})
    assert result["census_data"]["success"] is True
    assert result["answer_text"].startswith("Median household income")
