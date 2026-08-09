"""Map LangChain agent messages to legacy AgentExecutor result shape."""

from __future__ import annotations

from collections import deque
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from src.agents.runtime.contracts import AgentExecutionResult

_TEXT_BLOCK_TYPES = frozenset({"text", "output_text"})


def _extract_text_from_message_content(content: Any) -> str:
    """Normalize AIMessage.content from str or Responses API block lists."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block:
                text_parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "reasoning":
            continue
        if block_type in _TEXT_BLOCK_TYPES or "text" in block:
            text = block.get("text", "")
            if text:
                text_parts.append(text)

    if text_parts:
        return "\n".join(text_parts)
    return str(content)


def _tool_action(tool_name: str, tool_input: Any, tool_call_id: str | None):
    class _Action:
        def __init__(self) -> None:
            self.tool = tool_name
            self.tool_input = tool_input
            self.tool_call_id = tool_call_id

    return _Action()


def message_trace_to_executor_result(messages: list[BaseMessage]) -> AgentExecutionResult:
    """Convert create_agent message trace into {output, intermediate_steps}."""
    pending_by_id: dict[str, tuple[str, Any]] = {}
    pending_fifo: deque[tuple[str, Any]] = deque()
    intermediate_steps: list[tuple[Any, Any]] = []
    final_text = ""

    for message in messages:
        if isinstance(message, AIMessage):
            if message.content and not message.tool_calls:
                final_text = _extract_text_from_message_content(message.content)
            for call in message.tool_calls or []:
                tool_name = str(call.get("name", ""))
                tool_input = call.get("args") or {}
                call_id = call.get("id")
                if call_id:
                    pending_by_id[str(call_id)] = (tool_name, tool_input)
                else:
                    pending_fifo.append((tool_name, tool_input))
        elif isinstance(message, ToolMessage):
            call_id = message.tool_call_id or ""
            if call_id and call_id in pending_by_id:
                tool_name, tool_input = pending_by_id.pop(call_id)
            elif pending_fifo:
                tool_name, tool_input = pending_fifo.popleft()
            else:
                tool_name = message.name or "unknown_tool"
                tool_input = {}
            intermediate_steps.append((_tool_action(tool_name, tool_input, message.tool_call_id), message.content))

    if not final_text:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                final_text = _extract_text_from_message_content(message.content)
                break

    return AgentExecutionResult(output=final_text, intermediate_steps=intermediate_steps)
