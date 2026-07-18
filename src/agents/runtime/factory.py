"""Build the modern create_agent runtime backend."""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.agents.runtime.contracts import AgentRuntimeBackend

VALID_RUNTIMES = frozenset({"modern"})
DEFAULT_RUNTIME = "modern"


def resolve_agent_runtime() -> str:
    runtime = (os.getenv("AGENT_RUNTIME") or DEFAULT_RUNTIME).strip().lower()
    if runtime == "classic":
        raise ValueError(
            "AGENT_RUNTIME=classic was removed after A4 cutover; "
            "use modern (default) or unset AGENT_RUNTIME."
        )
    if runtime not in VALID_RUNTIMES:
        raise ValueError(f"Unknown AGENT_RUNTIME={runtime!r}; expected {DEFAULT_RUNTIME!r}")
    return runtime


def build_agent_backend(
    *,
    llm: BaseChatModel | None,
    tools: list[BaseTool],
    system_prompt: str,
) -> AgentRuntimeBackend:
    if llm is None:
        raise RuntimeError("Modern runtime requires an initialized LLM")
    from src.agents.runtime.modern_backend import ModernBackend

    return ModernBackend(llm=llm, tools=tools, system_prompt=system_prompt)
