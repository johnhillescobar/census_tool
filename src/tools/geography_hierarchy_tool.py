import json
import logging
import os
import sys
from typing import Dict, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.chroma_utils import get_hierarchy_ordering, initialize_chroma_client
from config import CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME

logger = logging.getLogger(__name__)


class GeographyHierarchyInput(BaseModel):
    """Input schema for geography hierarchy tool."""

    action: str = Field(
        default="get_hierarchy_ordering",
        description="Currently only get_hierarchy_ordering is supported.",
    )
    dataset: str = Field(..., description="Dataset path, e.g. acs/acs5")
    year: int = Field(..., description="Census year")
    for_level: str = Field(..., description="Target geography level (e.g. county)")
    parent_hint: Optional[List[str]] = Field(
        default=None, description="Optional expected parent ordering list"
    )
    include_metadata: bool = Field(
        default=False, description="Return raw metadata payload when True"
    )


class GeographyHierarchyTool(BaseTool):
    """
    Query geography hierarchy ordering from Chroma collection so the agent
    knows how to assemble for=/in= clauses.
    """

    name: str = "geography_hierarchy"
    description: str = """
    Look up geography hierarchy ordering for a dataset/year/for_level.

    Input must be valid JSON with:
    - action: "get_hierarchy_ordering" (default)
    - dataset: Dataset path (e.g., "acs/acs5")
    - year: Census year (e.g., 2023)
    - for_level: Target geography token (e.g., "county", "place")
    - parent_hint: Optional array to cross-check expected ordering
    - include_metadata: Optional bool to return raw metadata payload
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        try:
            params = (
                json.loads(tool_input) if isinstance(tool_input, str) else tool_input
            )
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON input - {exc}"

        try:
            payload = GeographyHierarchyInput(**params)
        except Exception as exc:
            return f"Error: {exc}"

        if payload.action != "get_hierarchy_ordering":
            return f"Error: Unsupported action '{payload.action}'"

        ordered_parents = get_hierarchy_ordering(
            payload.dataset, payload.year, payload.for_level
        )

        warnings: List[str] = []
        metadata = None
        example_url = None
        geography_hierarchy = None

        if not ordered_parents:
            warnings.append(
                f"No hierarchy ordering found for dataset {payload.dataset}, year {payload.year}, for_level {payload.for_level}."
            )
        else:
            # fetch extra metadata from collection for example URL / hierarchy string
            client = initialize_chroma_client()
            if isinstance(client, dict):
                warnings.append("Unable to connect to Chroma for metadata lookup.")
            else:
                try:
                    collection = client.get_collection(
                        CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME
                    )
                    result = collection.get(
                        where={
                            "$and": [
                                {"dataset": {"$eq": payload.dataset}},
                                {"year": {"$eq": payload.year}},
                                {"for_level": {"$eq": payload.for_level}},
                            ]
                        },
                        include=["metadatas"],
                    )
                    metadatas = result.get("metadatas") or []
                    if metadatas:
                        metadata = metadatas[0]
                        geography_hierarchy = metadata.get("geography_hierarchy")
                        example_url = metadata.get("example_url")
                except Exception as exc:
                    warnings.append(f"Metadata lookup failed: {exc}")

        if payload.parent_hint:
            hint = [hint.strip() for hint in payload.parent_hint]
            if ordered_parents and hint != ordered_parents:
                warnings.append(
                    f"parent_hint {hint} differs from stored ordering {ordered_parents}."
                )
            elif not ordered_parents:
                ordered_parents = hint  # fallback
                warnings.append("Using parent_hint as fallback ordering.")

        response: Dict[str, any] = {
            "ordered_parents": ordered_parents,
            "geography_hierarchy": geography_hierarchy,
            "example_url": example_url,
            "warnings": warnings,
        }

        if payload.include_metadata and metadata:
            response["metadata"] = metadata

        return json.dumps(response)


__all__ = ["GeographyHierarchyTool"]
