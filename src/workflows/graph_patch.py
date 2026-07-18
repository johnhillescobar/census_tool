"""Typed workflow patches projected at the LangGraph boundary."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.geography_contract import GeographyIntent
from src.domain.strict_json import JsonMap
from src.state.types import (
    FinalResponseState,
    WorkflowArtifactsState,
    artifacts_state_to_update,
    final_state_to_update,
)
from src.state.workflow_plan import WorkflowPlan


class CensusGraphPatch(BaseModel):
    """Optional CensusState delta; unset fields are omitted from LangGraph updates."""

    model_config = ConfigDict(extra="forbid")

    logs: list[str] | None = Field(default=None, description="Appended via list reducer when present.")
    error: str | None = Field(default=None, description="Error channel overwrite.")
    plan: WorkflowPlan | None = None
    final: FinalResponseState | None = None
    artifacts: WorkflowArtifactsState | None = None
    geo: GeographyIntent | None = None
    profile: JsonMap | None = None
    history: list[JsonMap] | None = None
    cache_index: JsonMap | None = None

    def as_langgraph_update(self) -> dict[str, Any]:
        """Project typed fields to the current LangGraph-compatible update map."""
        patch: dict[str, Any] = {}
        for name in self.model_fields_set:
            value = getattr(self, name)
            if value is None:
                continue
            if name == "final":
                patch[name] = final_state_to_update(value)
            elif name == "artifacts":
                patch[name] = artifacts_state_to_update(value)
            elif name == "geo":
                patch[name] = value
            elif isinstance(value, JsonMap):
                patch[name] = value.root
            elif isinstance(value, list) and value and isinstance(value[0], JsonMap):
                patch[name] = [item.root for item in value]
            else:
                patch[name] = value
        return patch
