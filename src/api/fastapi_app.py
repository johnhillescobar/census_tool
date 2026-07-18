"""FastAPI + SSE adapter over the Census LangGraph workflow."""

from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app import create_census_graph
from src.api.contracts import HealthResponse, QueryRequest, QueryResponse
from src.services.graph_session import (
    build_turn_state_for_thread,
    resolve_thread_id,
    runnable_config,
)

app = FastAPI(title="Census Tool API", version="0.1.0")
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = create_census_graph()
    return _graph


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    thread_id = resolve_thread_id(
        thread_id=request.thread_id,
        new_thread=request.new_thread,
    )
    graph = get_graph()
    config = runnable_config(user_id=request.user_id, thread_id=thread_id)
    state = build_turn_state_for_thread(graph, request.question, config=config)
    result = graph.invoke(state, config)
    return QueryResponse(thread_id=thread_id, result=result)


@app.post("/query/stream")
def query_stream(request: QueryRequest) -> StreamingResponse:
    thread_id = resolve_thread_id(
        thread_id=request.thread_id,
        new_thread=request.new_thread,
    )
    graph = get_graph()
    config = runnable_config(user_id=request.user_id, thread_id=thread_id)
    state = build_turn_state_for_thread(graph, request.question, config=config)

    def event_generator():
        yield f"event: started\ndata: {json.dumps({'thread_id': thread_id})}\n\n"
        result = graph.invoke(state, config)
        payload = {"thread_id": thread_id, "result": result}
        yield f"event: completed\ndata: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    host = os.getenv("CENSUS_API_HOST", "127.0.0.1")
    port = int(os.getenv("CENSUS_API_PORT", "8000"))
    uvicorn.run("src.api.fastapi_app:app", host=host, port=port, reload=False)
