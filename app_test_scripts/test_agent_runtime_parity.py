"""Offline contract parity checks for modern runtime adapter + parser."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agents.adapters.message_to_executor import message_trace_to_executor_result
from src.agents.census_query_agent import CensusQueryAgent


def _success_trace(*, answer_text: str = "Median income for 2020."):
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "abc",
                    "name": "strict_census_api_call",
                    "args": {"year": 2020, "dataset": "acs/acs5"},
                }
            ],
        ),
        ToolMessage(
            content='{"success": true, "data": [["Year", "Income"], [2020, 70000]]}',
            tool_call_id="abc",
            name="strict_census_api_call",
        ),
        AIMessage(
            content=json.dumps(
                {
                    "answer_text": answer_text,
                    "census_data": {"success": True, "data": [["Year", "Income"], [2020, 70000]]},
                    "data_summary": "ACS 2020",
                    "reasoning_trace": "stub",
                    "charts_needed": [],
                    "tables_needed": [],
                    "footnotes": [],
                    "comparison_input_rows": [],
                }
            )
        ),
    ]


def _clarification_trace():
    return [
        AIMessage(
            content=json.dumps(
                {
                    "answer_text": "Which geography should I use for this comparison?",
                    "census_data": {"success": False, "data": []},
                    "data_summary": "Needs geography clarification",
                    "reasoning_trace": "stub",
                    "charts_needed": [],
                    "tables_needed": [],
                    "footnotes": [],
                    "comparison_input_rows": [],
                }
            )
        ),
    ]


def _invalid_geography_trace():
    return [
        AIMessage(
            content="",
            tool_calls=[{"id": "geo", "name": "resolve_area_name", "args": {"name": "Mars"}}],
        ),
        ToolMessage(content="Area not found in Census data", tool_call_id="geo", name="resolve_area_name"),
        AIMessage(
            content=json.dumps(
                {
                    "answer_text": "Unable to resolve geography.",
                    "census_data": {"success": False, "data": []},
                    "data_summary": "Geography failure",
                    "reasoning_trace": "stub",
                    "charts_needed": [],
                    "tables_needed": [],
                    "footnotes": [],
                    "comparison_input_rows": [],
                }
            )
        ),
    ]


@pytest.mark.parametrize(
    "messages,expected_success,expected_fragment",
    [
        (_success_trace(), True, "Median income"),
        (_clarification_trace(), False, "Which geography"),
        (_invalid_geography_trace(), False, "unable to complete"),
    ],
    ids=["success", "clarification", "invalid_geography"],
)
def test_modern_adapter_fixtures_parse_to_expected_contract(
    messages,
    expected_success,
    expected_fragment,
):
    agent = CensusQueryAgent(allow_offline=True)
    execution = message_trace_to_executor_result(messages)
    parsed = agent._parse_solution(
        {
            "output": execution.output,
            "intermediate_steps": execution.intermediate_steps,
        }
    )
    assert parsed["census_data"]["success"] is expected_success
    assert expected_fragment in parsed["answer_text"]


def test_strict_census_observation_preserved_in_adapter_output():
    messages = _success_trace()
    execution = message_trace_to_executor_result(messages)
    assert len(execution.intermediate_steps) == 1
    action, observation = execution.intermediate_steps[0]
    assert action.tool == "strict_census_api_call"
    assert "70000" in str(observation)
