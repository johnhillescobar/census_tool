"""Agent tool to submit a grounded candidate-ID selection for harness validation."""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, ValidationError

from src.domain.retrieval_plan import GroundedSelection
from src.tools.json_parse import parse_first_json


class ProposeGroundedPlanTool(BaseTool):
    """Accept a GroundedSelection payload referencing prior retrieval evidence IDs."""

    name: str = "propose_grounded_plan"
    description: str = """
    Submit a grounded planning selection using candidate IDs from retrieval_evidence.
    Input must be valid JSON matching the GroundedSelection contract:
    - selection_id: opaque selection identifier
    - status: "selected", "ambiguous", or "rejected"
    - evidence_ids: list of evidence_id values from prior retrieval tool outputs
    - selected_table_ids, selected_hierarchy_id, selected_area_ids as applicable
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        try:
            payload = parse_first_json(tool_input) if isinstance(tool_input, str) else tool_input
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON input - {exc}"

        try:
            selection = GroundedSelection.model_validate(payload)
        except ValidationError as exc:
            return f"Error: invalid grounded selection - {exc}"

        return json.dumps(
            {
                "status": "accepted",
                "proposed_selection": selection.model_dump(mode="json"),
            }
        )


__all__ = ["ProposeGroundedPlanTool"]
