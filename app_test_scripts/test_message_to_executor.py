"""Adapter tests for modern runtime message pairing."""

import json

from langchain_core.messages import AIMessage, ToolMessage

from src.agents.adapters.message_to_executor import (
    _extract_text_from_message_content,
    message_trace_to_executor_result,
)
from src.agents.census_query_agent import CensusQueryAgent


def _execution_final_answer_payload(*, answer_text: str = "Median income for 2020."):
    return json.dumps(
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


def _responses_api_execution_content(final_text: str) -> list[dict]:
    """Fixture resembling GPT-5.5 Responses API execution-turn content blocks."""
    return [
        {
            "type": "reasoning",
            "id": "rs_abc123",
            "summary": [{"type": "summary_text", "text": "Checked census table B19013."}],
        },
        {"type": "text", "text": final_text, "annotations": [], "id": "msg_abc123"},
    ]


def test_extract_text_from_responses_api_block_list():
    final_json = _execution_final_answer_payload()
    content = _responses_api_execution_content(final_json)
    extracted = _extract_text_from_message_content(content)
    assert extracted == final_json


def test_message_trace_extracts_responses_api_block_list_for_parser():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "strict_census_api_call",
                    "args": {"year": 2020},
                }
            ],
        ),
        ToolMessage(content='{"success": true}', tool_call_id="call_1", name="strict_census_api_call"),
        AIMessage(content=_responses_api_execution_content(_execution_final_answer_payload())),
    ]
    execution = message_trace_to_executor_result(messages)
    parsed = CensusQueryAgent(allow_offline=True)._parse_solution(
        {
            "output": execution.output,
            "intermediate_steps": execution.intermediate_steps,
        }
    )
    assert parsed["census_data"]["success"] is True
    assert "Median income" in parsed["answer_text"]


def test_message_trace_planning_turn_reasoning_blocks_unaffected():
    planning_text = "Planning complete. Next step: run census tools."
    messages = [
        AIMessage(
            content=[
                {"type": "reasoning", "id": "rs_plan", "summary": []},
                {"type": "text", "text": planning_text},
            ]
        ),
    ]
    execution = message_trace_to_executor_result(messages)
    assert execution.output == planning_text
    parsed = CensusQueryAgent(allow_offline=True)._parse_solution({"output": execution.output})
    assert parsed["census_data"]["success"] is False


def test_message_trace_pairs_tool_calls_with_observations():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "strict_census_api_call",
                    "args": {"year": 2020},
                }
            ],
        ),
        ToolMessage(content='{"success": true}', tool_call_id="call_1", name="strict_census_api_call"),
        AIMessage(content='Final Answer: {"answer_text":"done"}'),
    ]
    result = message_trace_to_executor_result(messages)
    assert len(result.intermediate_steps) == 1
    action, observation = result.intermediate_steps[0]
    assert action.tool == "strict_census_api_call"
    assert "done" in result.output


def test_message_trace_preserves_multiple_tool_calls_in_order():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {"id": "a", "name": "resolve_area_name", "args": {"name": "California"}},
                {"id": "b", "name": "strict_census_api_call", "args": {"year": 2020}},
            ],
        ),
        ToolMessage(content='{"matches":[]}', tool_call_id="a", name="resolve_area_name"),
        ToolMessage(content='{"success": true}', tool_call_id="b", name="strict_census_api_call"),
        AIMessage(content='{"answer_text":"ok"}'),
    ]
    result = message_trace_to_executor_result(messages)
    assert len(result.intermediate_steps) == 2
    assert result.intermediate_steps[0][0].tool == "resolve_area_name"
    assert result.intermediate_steps[1][0].tool == "strict_census_api_call"


def test_message_trace_handles_missing_tool_call_id():
    messages = [
        ToolMessage(content='{"success": false}', tool_call_id="", name="census_api_call"),
        AIMessage(content='{"answer_text":"failed"}'),
    ]
    result = message_trace_to_executor_result(messages)
    assert len(result.intermediate_steps) == 1
    assert result.intermediate_steps[0][0].tool == "census_api_call"


def test_message_trace_pairs_idless_duplicate_tool_names_in_fifo_order():
    messages = [
        AIMessage.model_construct(
            content="",
            tool_calls=[
                {"name": "strict_census_api_call", "args": {"year": 2020}},
                {"name": "strict_census_api_call", "args": {"year": 2021}},
            ],
        ),
        ToolMessage(content='{"year": 2020}', tool_call_id="", name="strict_census_api_call"),
        ToolMessage(content='{"year": 2021}', tool_call_id="", name="strict_census_api_call"),
        AIMessage(content='{"answer_text":"ok"}'),
    ]
    result = message_trace_to_executor_result(messages)
    assert len(result.intermediate_steps) == 2
    assert result.intermediate_steps[0][0].tool_input == {"year": 2020}
    assert result.intermediate_steps[1][0].tool_input == {"year": 2021}
