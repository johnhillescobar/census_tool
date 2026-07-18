"""Classic AgentExecutor backend (langchain-classic compatibility)."""

from __future__ import annotations

from langchain_classic.agents import AgentExecutor

from src.agents.runtime.contracts import AgentExecutionResult, AgentRuntimeBackend
from src.services.conversation_summarizer import summarize_intermediate_steps


class ClassicBackend(AgentRuntimeBackend):
    def __init__(self, agent_executor: AgentExecutor):
        self._executor = agent_executor

    def invoke(self, executor_input: str) -> AgentExecutionResult:
        raw = self._executor.invoke({"input": executor_input})
        intermediate_steps = raw.get("intermediate_steps", [])
        if len(intermediate_steps) > 10:
            intermediate_steps = summarize_intermediate_steps(intermediate_steps, keep_recent=5)
        return AgentExecutionResult(
            output=str(raw.get("output", "")),
            intermediate_steps=list(intermediate_steps),
        )
