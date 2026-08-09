"""Extract grounded clarification selections from agent tool steps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

SELECT_CLARIFICATION_TOOL = "select_clarification_option"


@dataclass(frozen=True)
class ClarificationSelection:
    """Agent-validated clarification choice grounded in preserved evidence."""

    candidate_id: str
    option_id: str
    label: str


def extract_clarification_selection(agent_result: dict[str, Any]) -> ClarificationSelection | None:
    """Return agent-validated selection from an accepted select_clarification_option tool call."""
    for step in agent_result.get("intermediate_steps") or []:
        if not step or len(step) < 2:
            continue
        tool_call = step[0]
        observation = step[1]
        tool_name = getattr(tool_call, "tool", None)
        if tool_name != SELECT_CLARIFICATION_TOOL:
            continue
        payload = observation
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue
        if not isinstance(payload, dict) or payload.get("status") != "accepted":
            continue
        candidate_id = payload.get("candidate_id")
        option_id = payload.get("option_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        if not isinstance(option_id, str) or not option_id:
            continue
        label = payload.get("label")
        return ClarificationSelection(
            candidate_id=candidate_id,
            option_id=option_id,
            label=label if isinstance(label, str) else "",
        )
    return None


__all__ = ["SELECT_CLARIFICATION_TOOL", "ClarificationSelection", "extract_clarification_selection"]
