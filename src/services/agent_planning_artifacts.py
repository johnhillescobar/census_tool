"""Collect grounded planning artifacts from agent tool intermediate steps (CENSUS-41)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence
from src.tools.json_parse import parse_first_json

PROPOSE_GROUNDED_PLAN_TOOL = "propose_grounded_plan"


def _coerce_json(payload: Any) -> Any | None:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return None
        try:
            return parse_first_json(text)
        except json.JSONDecodeError:
            return None
    return None


def _coerce_retrieval_evidence(payload: Any) -> RetrievalEvidence | None:
    data = _coerce_json(payload)
    if not isinstance(data, dict):
        return None
    try:
        return RetrievalEvidence.model_validate(data)
    except ValidationError:
        return None


def _coerce_grounded_selection(payload: Any) -> GroundedSelection | None:
    data = _coerce_json(payload)
    if not isinstance(data, dict):
        return None
    if "proposed_selection" in data and isinstance(data["proposed_selection"], dict):
        data = data["proposed_selection"]
    try:
        return GroundedSelection.model_validate(data)
    except ValidationError:
        return None


def _extract_evidence_items(payload: Any) -> list[RetrievalEvidence]:
    data = _coerce_json(payload)
    if data is None:
        return []

    direct = _coerce_retrieval_evidence(data)
    if direct is not None:
        return [direct]

    if not isinstance(data, dict):
        return []

    items: list[RetrievalEvidence] = []
    embedded = data.get("retrieval_evidence")
    if embedded is not None:
        if isinstance(embedded, list):
            for item in embedded:
                evidence = _coerce_retrieval_evidence(item)
                if evidence is not None:
                    items.append(evidence)
        else:
            evidence = _coerce_retrieval_evidence(embedded)
            if evidence is not None:
                items.append(evidence)

    for key in ("hierarchy_evidence", "area_evidence"):
        embedded = data.get(key)
        if embedded is None:
            continue
        if isinstance(embedded, list):
            for item in embedded:
                evidence = _coerce_retrieval_evidence(item)
                if evidence is not None:
                    items.append(evidence)
        else:
            evidence = _coerce_retrieval_evidence(embedded)
            if evidence is not None:
                items.append(evidence)

    return items


def collect_planning_artifacts(
    intermediate_steps: list[Any] | None,
) -> tuple[list[RetrievalEvidence], GroundedSelection | None]:
    """Merge retrieval evidence and the latest grounded selection from agent tool steps."""
    evidence_by_id: dict[str, RetrievalEvidence] = {}
    selection: GroundedSelection | None = None

    for step in intermediate_steps or []:
        if not step or len(step) < 2:
            continue
        action, observation = step[0], step[1]
        tool_name = getattr(action, "tool", None)

        for evidence in _extract_evidence_items(observation):
            evidence_by_id[evidence.evidence_id] = evidence

        if tool_name == PROPOSE_GROUNDED_PLAN_TOOL:
            tool_input = getattr(action, "tool_input", None)
            parsed = _coerce_grounded_selection(tool_input) or _coerce_grounded_selection(observation)
            if parsed is not None:
                selection = parsed

    return list(evidence_by_id.values()), selection


__all__ = ["PROPOSE_GROUNDED_PLAN_TOOL", "collect_planning_artifacts"]
