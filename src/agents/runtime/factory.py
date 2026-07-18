"""Select classic or modern agent runtime backend."""

from __future__ import annotations

import os

from langchain_classic.agents import AgentExecutor
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.agents.runtime.classic_backend import ClassicBackend
from src.agents.runtime.contracts import AgentRuntimeBackend
from src.agents.runtime.modern_backend import ModernBackend

VALID_RUNTIMES = frozenset({"classic", "modern"})


def resolve_agent_runtime() -> str:
    runtime = (os.getenv("AGENT_RUNTIME") or "modern").strip().lower()
    if runtime not in VALID_RUNTIMES:
        raise ValueError(f"Unknown AGENT_RUNTIME={runtime!r}; expected one of {sorted(VALID_RUNTIMES)}")
    return runtime


def build_agent_backend(
    *,
    runtime: str,
    agent_executor: AgentExecutor | None,
    llm: BaseChatModel | None,
    tools: list[BaseTool],
    system_prompt: str,
) -> AgentRuntimeBackend:
    if runtime == "classic":
        if agent_executor is None:
            raise RuntimeError("Classic runtime requires an initialized AgentExecutor")
        return ClassicBackend(agent_executor)
    if llm is None:
        raise RuntimeError("Modern runtime requires an initialized LLM")
    return ModernBackend(llm=llm, tools=tools, system_prompt=system_prompt)
