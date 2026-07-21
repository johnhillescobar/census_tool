"""Typed diagnostics for grounded Census retrieval and planning."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RetrievalStage(StrEnum):
    ANALYSIS = "analysis"
    TABLE_RETRIEVAL = "table_retrieval"
    GEOGRAPHY_RETRIEVAL = "geography_retrieval"
    GROUNDED_SELECTION = "grounded_selection"
    PLAN_VALIDATION = "plan_validation"
    CLARIFICATION = "clarification"
    API_GUARD = "api_guard"


class RetrievalStatus(StrEnum):
    STARTED = "started"
    HIT = "hit"
    EMPTY = "empty"
    RESOLVED = "resolved"
    CLARIFICATION_REQUIRED = "clarification_required"
    REJECTED = "rejected"
    ERROR = "error"


class RetrievalCandidateTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    score: float | None = None
    display_name: str | None = None


class RetrievalTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: RetrievalStage
    status: RetrievalStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason_code: str | None = None
    collection: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    candidates: list[RetrievalCandidateTrace] = Field(default_factory=list)
    selected_ids: list[str] = Field(default_factory=list)
    latency_ms: float | None = Field(default=None, ge=0)
    warning: str | None = None
    error: str | None = None
    index_version: str | None = None


class RetrievalTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    prompt_version: str | None = None
    events: list[RetrievalTraceEvent] = Field(default_factory=list)

    def append(self, event: RetrievalTraceEvent) -> None:
        self.events.append(event)

    def compact_summary(self) -> list[str]:
        return [f"{event.stage.value}:{event.status.value}" for event in self.events]


__all__ = [
    "RetrievalCandidateTrace",
    "RetrievalStage",
    "RetrievalStatus",
    "RetrievalTrace",
    "RetrievalTraceEvent",
]
