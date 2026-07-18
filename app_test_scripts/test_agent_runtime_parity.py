"""Offline parity checks between classic and modern runtime adapters."""

import json

from langchain_core.messages import AIMessage, ToolMessage

from src.agents.adapters.message_to_executor import message_trace_to_executor_result
from src.agents.census_query_agent import CensusQueryAgent


def _fixture_trace():
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
            content='{"success": true, "records": []}',
            tool_call_id="abc",
            name="strict_census_api_call",
        ),
        AIMessage(
            content=json.dumps(
                {
                    "answer_text": "Median income for 2020.",
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


def test_strict_census_observation_preserved_in_adapter_output():
    messages = _fixture_trace()
    classic_shape = message_trace_to_executor_result(messages)
    modern_shape = message_trace_to_executor_result(messages)
    assert classic_shape.output == modern_shape.output
    assert len(classic_shape.intermediate_steps) == len(modern_shape.intermediate_steps)


def test_shared_parser_accepts_adapter_output_for_both_runtimes():
    agent = CensusQueryAgent(allow_offline=True)
    execution = message_trace_to_executor_result(_fixture_trace())
    parsed = agent._parse_solution(
        {
            "output": execution.output,
            "intermediate_steps": execution.intermediate_steps,
        }
    )
    assert parsed["census_data"]["success"] is True
    assert "Median income" in parsed["answer_text"]
