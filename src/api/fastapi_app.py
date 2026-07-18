"""FastAPI + SSE adapter over the Census LangGraph workflow."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import create_census_graph
from src.services.graph_session import (
    build_delta_turn_state,
    build_fresh_thread_state,
    new_thread_id,
    runnable_config,
)

app = FastAPI(title="Census Tool API", version="0.1.0")
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = create_census_graph()
    return _graph


class QueryRequest(BaseModel):
    user_id: str = "demo"
    thread_id: str | None = None
    question: str
    new_thread: bool = False


class QueryResponse(BaseModel):
    thread_id: str
    result: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    thread_id = request.thread_id or new_thread_id()
    if request.new_thread:
        state = build_fresh_thread_state(request.question)
    else:
        state = build_delta_turn_state(request.question)
    config = runnable_config(user_id=request.user_id, thread_id=thread_id)
    result = get_graph().invoke(state, config)
    return QueryResponse(thread_id=thread_id, result=result)


@app.post("/query/stream")
def query_stream(request: QueryRequest) -> StreamingResponse:
    thread_id = request.thread_id or new_thread_id()
    state = build_fresh_thread_state(request.question) if request.new_thread else build_delta_turn_state(request.question)
    config = runnable_config(user_id=request.user_id, thread_id=thread_id)

    def event_generator():
        yield f"event: started\ndata: {json.dumps({'thread_id': thread_id})}\n\n"
        result = get_graph().invoke(state, config)
        payload = {"thread_id": thread_id, "result": result}
        yield f"event: completed\ndata: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    host = os.getenv("CENSUS_API_HOST", "127.0.0.1")
    port = int(os.getenv("CENSUS_API_PORT", "8000"))
    uvicorn.run("src.api.fastapi_app:app", host=host, port=port, reload=False)
