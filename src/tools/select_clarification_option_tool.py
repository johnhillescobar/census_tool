"""Agent tool to map a clarification reply to one grounded pending option."""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from src.domain.agent_clarification_context import AgentClarificationContext
from src.tools.json_parse import parse_first_json


class SelectClarificationOptionTool(BaseTool):
    """Accept a grounded option_id or candidate_id from the pending clarification context."""

    name: str = "select_clarification_option"
    description: str = """
    Map the user's clarification reply to one grounded pending option.
    Input must be valid JSON with exactly one of:
    - option_id: pending option id (e.g. "table_0", "geo_1")
    - candidate_id: grounded candidate id from retrieval evidence

    The harness validates the selection against preserved evidence. Do not invent ids.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    active_context: AgentClarificationContext | None = None

    def bind_context(self, context: AgentClarificationContext | None) -> None:
        self.active_context = context

    def _run(self, tool_input: str) -> str:
        if self.active_context is None:
            return json.dumps({"status": "rejected", "reason": "no active clarification context"})

        try:
            payload = parse_first_json(tool_input) if isinstance(tool_input, str) else tool_input
        except json.JSONDecodeError as exc:
            return json.dumps({"status": "rejected", "reason": f"invalid JSON: {exc}"})

        if not isinstance(payload, dict):
            return json.dumps({"status": "rejected", "reason": "input must be a JSON object"})

        option_id = payload.get("option_id")
        candidate_id = payload.get("candidate_id")
        if bool(option_id) == bool(candidate_id):
            return json.dumps({"status": "rejected", "reason": "provide exactly one of option_id or candidate_id"})

        pending = self.active_context.pending_options
        allowed_ids = {option.option_id for option in pending}
        allowed_candidates = {option.candidate_id for option in pending}

        if option_id is not None:
            if option_id not in allowed_ids:
                return json.dumps({"status": "rejected", "reason": f"unknown option_id: {option_id}"})
            selected = next(option for option in pending if option.option_id == option_id)
        else:
            if candidate_id not in allowed_candidates:
                return json.dumps({"status": "rejected", "reason": f"unknown candidate_id: {candidate_id}"})
            selected = next(option for option in pending if option.candidate_id == candidate_id)

        return json.dumps(
            {
                "status": "accepted",
                "option_id": selected.option_id,
                "candidate_id": selected.candidate_id,
                "label": selected.label,
            }
        )


__all__ = ["SelectClarificationOptionTool"]
