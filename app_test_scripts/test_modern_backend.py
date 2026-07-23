"""Modern backend unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage

from src.agents.runtime.modern_backend import ModernBackend


def test_modern_backend_invoke_maps_message_trace_to_executor_result():
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
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
            ToolMessage(
                content='{"success": true, "data": []}',
                tool_call_id="call_1",
                name="strict_census_api_call",
            ),
            AIMessage(
                content=json.dumps(
                    {
                        "answer_text": "Population data retrieved.",
                        "census_data": {"success": True, "data": [["Year", "Pop"], [2020, 100]]},
                        "data_summary": "stub",
                        "reasoning_trace": "stub",
                        "charts_needed": [],
                        "tables_needed": [],
                        "footnotes": [],
                        "comparison_input_rows": [],
                    }
                )
            ),
        ]
    }

    mock_llm = MagicMock()
    with patch("src.agents.runtime.modern_backend.create_agent", return_value=mock_agent):
        backend = ModernBackend(llm=mock_llm, tools=[], system_prompt="test prompt")
        result = backend.invoke("User query: population")

    assert "Population data retrieved" in result.output
    assert len(result.intermediate_steps) == 1
    action, observation = result.intermediate_steps[0]
    assert action.tool == "strict_census_api_call"
    assert observation == '{"success": true, "data": []}'
    mock_agent.invoke.assert_called_once_with({"messages": [{"role": "user", "content": "User query: population"}]})


def test_modern_backend_configures_call_limit_middleware():
    mock_llm = MagicMock()
    with patch("src.agents.runtime.modern_backend.create_agent") as mock_create:
        ModernBackend(
            llm=mock_llm,
            tools=[],
            system_prompt="limits",
            max_model_calls=12,
            max_tool_calls=8,
        )
    kwargs = mock_create.call_args.kwargs
    assert kwargs["system_prompt"] == "limits"
    assert len(kwargs["middleware"]) == 2
