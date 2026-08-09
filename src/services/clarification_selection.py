"""Extract grounded clarification selections from agent tool steps."""

from __future__ import annotations

import json
from typing import Any

SELECT_CLARIFICATION_TOOL = "select_clarification_option"


def extract_clarification_selection(agent_result: dict[str, Any]) -> str | None:
    """Return harness-ready selection text from an accepted select_clarification_option tool call."""
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
        option_id = payload.get("option_id")
        if isinstance(option_id, str) and option_id:
            return option_id
    return None


__all__ = ["SELECT_CLARIFICATION_TOOL", "extract_clarification_selection"]
