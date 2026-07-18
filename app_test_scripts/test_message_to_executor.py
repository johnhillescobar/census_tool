"""Adapter tests for modern runtime message pairing."""

from langchain_core.messages import AIMessage, ToolMessage

from src.agents.adapters.message_to_executor import message_trace_to_executor_result


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
