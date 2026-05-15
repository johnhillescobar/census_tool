"""Typed partial updates emitted by LangGraph workflow nodes (Track 2E).

LangGraph merges these dicts into ``CensusState``. This module is the single
framework-edge adapter from typed patches to LangGraph update maps.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.strict_json import JsonMap
from src.state.types import (
    FinalResponseState,
    WorkflowArtifactsState,
    WorkflowPlanState,
)


class CensusGraphPatch(BaseModel):
    """Optional CensusState delta; unset fields are omitted from the LangGraph merge."""

    model_config = ConfigDict(extra="forbid")

    logs: list[str] | None = Field(
        default=None, description="Appended via list reducer when present."
    )
    error: str | None = Field(default=None, description="Error channel overwrite.")
    plan: WorkflowPlanState | None = None
    final: FinalResponseState | None = None
    artifacts: WorkflowArtifactsState | None = None
    profile: JsonMap | None = None
    history: list[JsonMap] | None = None
    cache_index: JsonMap | None = None

    def as_langgraph_update(self) -> dict[str, object]:
        """Projection for LangGraph ``add_messages`` / reducers."""
        patch: dict[str, object] = {}
        # Keep nested Pydantic models as instances so partial ``WorkflowArtifactsState``
        # patches round-trip through ``CensusState`` validators/reducers correctly.
        # (``model_dump`` can produce StrictCensusApiResponse dicts missing required nodes.)
        for name in self.model_fields_set:
            value = getattr(self, name)
            if value is None:
                continue
            patch[name] = value
        return patch
