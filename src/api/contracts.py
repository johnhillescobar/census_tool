"""FastAPI request/response contracts for the Census Tool API (Phase 5)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    user_id: str = "demo"
    thread_id: str | None = None
    question: str
    new_thread: bool = False


class QueryResponse(BaseModel):
    thread_id: str
    result: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
