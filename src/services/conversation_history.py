"""Conversation history payloads for Streamlit session state and session PDF (PdfConversationEntry shape)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.domain.census_tool_contract import StrictCensusApiResponse
from src.domain.presentation_contract import PresentationKind
from src.services.presentation_routing import compute_presentation_routing
from src.state.types import (
    CensusState,
    FinalResponseState,
    WorkflowArtifactsState,
)


def pdf_conversation_result_dict(state: CensusState) -> dict[str, Any]:
    """Subset of graph state expected by ``PdfConversationResult`` / session PDF."""
    return {
        "final": state.final.model_dump(mode="json") if state.final else None,
        "artifacts": state.artifacts.model_dump(mode="json"),
        "logs": list(state.logs),
        "error": state.error,
    }


def census_state_from_pdf_history_entry(entry: dict[str, Any]) -> CensusState:
    """
    Rebuild a minimal ``CensusState`` from a Streamlit history entry.

    History stores only ``PdfConversationResult`` fields under ``result`` (no ``plan``),
    so clarification routing may not match the live graph for those turns.
    """
    q = entry.get("question")
    r = entry.get("result") or {}
    artifacts_raw = r.get("artifacts")
    final_raw = r.get("final")
    return CensusState(
        messages=[],
        original_query=q if isinstance(q, str) else None,
        intent=None,
        geo={},
        candidates={},
        plan=None,
        artifacts=(
            WorkflowArtifactsState.model_validate(artifacts_raw)
            if artifacts_raw
            else WorkflowArtifactsState()
        ),
        final=(
            FinalResponseState.model_validate(final_raw) if final_raw else None
        ),
        logs=list(r.get("logs") or []),
        error=r.get("error"),
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )


def history_entry_presentation_kind(entry: dict[str, Any]) -> PresentationKind:
    """Deterministic routing label for sidebar preview (matches main panel when plan is absent)."""
    state = census_state_from_pdf_history_entry(entry)
    return compute_presentation_routing(state).kind


def infer_streamlit_line_xy(
    df: pd.DataFrame,
    cd: StrictCensusApiResponse,
) -> tuple[str, str]:
    """
    Pick x/y columns for a Streamlit line chart from an adapter-produced frame.
    Raises ``ValueError`` if inference fails (caller may fall back to legacy record projection).
    """
    if df.empty or len(df.columns) < 1:
        raise ValueError("empty dataframe")

    cols = [str(c) for c in df.columns]

    def is_yearish(name: str) -> bool:
        n = name.lower()
        return n in ("year", "time", "date") or "year" in n

    yearish = [c for c in cols if is_yearish(c)]
    x_col = yearish[0] if yearish else cols[0]

    y_col = ""
    if cd.request is not None and cd.request.variables:
        for v in cd.request.variables:
            vs = str(v)
            if vs in df.columns and vs != x_col:
                y_col = vs
                break

    if not y_col:
        for c in cols:
            if c == x_col:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                y_col = c
                break

    if not y_col:
        for c in cols:
            if c != x_col:
                y_col = c
                break

    if not x_col or not y_col:
        raise ValueError("cannot infer line chart columns")

    return x_col, y_col
