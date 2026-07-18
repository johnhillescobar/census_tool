"""Modern create_agent backend."""

from __future__ import annotations

from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.agents.runtime.contracts import AgentExecutionResult, AgentRuntimeBackend


class ModernBackend(AgentRuntimeBackend):
    def __init__(
        self,
        *,
        llm: BaseChatModel,
        tools: list[BaseTool],
        system_prompt: str,
        max_model_calls: int = 40,
        max_tool_calls: int = 30,
    ):
        middleware = [
            ModelCallLimitMiddleware(run_limit=max_model_calls),
            ToolCallLimitMiddleware(run_limit=max_tool_calls),
        ]
        self._agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            middleware=middleware,
        )

    def invoke(self, executor_input: str) -> AgentExecutionResult:
        from src.agents.adapters.message_to_executor import message_trace_to_executor_result

        result = self._agent.invoke({"messages": [{"role": "user", "content": executor_input}]})
        messages = cast(list[Any], result.get("messages") or [])
        return message_trace_to_executor_result(messages)
