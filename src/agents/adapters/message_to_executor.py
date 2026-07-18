"""Map LangChain agent messages to legacy AgentExecutor result shape."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from src.agents.runtime.contracts import AgentExecutionResult


def _tool_action(tool_name: str, tool_input: Any, tool_call_id: str | None):
    class _Action:
        def __init__(self) -> None:
            self.tool = tool_name
            self.tool_input = tool_input
            self.tool_call_id = tool_call_id

    return _Action()


def message_trace_to_executor_result(messages: list[BaseMessage]) -> AgentExecutionResult:
    """Convert create_agent message trace into {output, intermediate_steps}."""
    pending_calls: dict[str, tuple[str, Any]] = {}
    intermediate_steps: list[tuple[Any, Any]] = []
    final_text = ""

    for message in messages:
        if isinstance(message, AIMessage):
            if message.content and not message.tool_calls:
                if isinstance(message.content, str):
                    final_text = message.content
                else:
                    final_text = str(message.content)
            for call in message.tool_calls or []:
                call_id = call.get("id") or call.get("name") or ""
                pending_calls[str(call_id)] = (
                    str(call.get("name", "")),
                    call.get("args") or {},
                )
        elif isinstance(message, ToolMessage):
            call_id = message.tool_call_id or ""
            tool_name, tool_input = pending_calls.pop(str(call_id), (message.name or "unknown_tool", {}))
            intermediate_steps.append((_tool_action(tool_name, tool_input, message.tool_call_id), message.content))

    if not final_text:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                final_text = str(message.content)
                break

    return AgentExecutionResult(output=final_text, intermediate_steps=intermediate_steps)
