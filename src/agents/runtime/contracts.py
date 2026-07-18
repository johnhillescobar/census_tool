"""Typed contracts for agent runtime backends."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class AgentExecutionResult(BaseModel):
    """Normalized executor output consumed by CensusQueryAgent._parse_solution."""

    model_config = ConfigDict(extra="forbid")

    output: str = ""
    intermediate_steps: list[tuple[Any, Any]] = Field(default_factory=list)


class AgentRuntimeBackend(Protocol):
    """Runtime seam behind CensusQueryAgent.solve()."""

    def invoke(self, executor_input: str) -> AgentExecutionResult: ...
