"""Chroma table retrieval tool returning typed RetrievalEvidence for planning."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, Field

from src.services.chroma_catalog_retriever import retrieve_table_candidates
from src.tools.json_parse import parse_first_json

logger = logging.getLogger(__name__)


class TableCatalogRetrievalTool(BaseTool):
    """Semantic table catalog search that returns grounded retrieval evidence."""

    name: str = "table_catalog_retrieval"
    description: str = """
    Search the Chroma table catalog for candidate tables matching a concept.
    Returns typed retrieval_evidence with opaque candidate IDs for planning.

    Input must be valid JSON with:
    - query: semantic search text (required)
    - dataset: Census dataset path (default: "acs/acs5")
    - year: Census year filter (default: 2023)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    chroma_client: Any = Field(default=None, exclude=True)

    def _run(self, tool_input: str) -> str:
        try:
            params = parse_first_json(tool_input) if isinstance(tool_input, str) else tool_input
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON input - {exc}"

        query = str(params.get("query", "")).strip()
        if not query:
            return "Error: 'query' parameter is required"

        dataset = params.get("dataset", "acs/acs5")
        raw_year = params.get("year", 2023)
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            return f"Error: 'year' must be an integer, got {raw_year!r}"
        logger.info("TableCatalogRetrievalTool query=%r dataset=%s year=%s", query, dataset, year)
        evidence = retrieve_table_candidates(
            query,
            dataset=dataset,
            year=year,
            client=self.chroma_client,
        )
        return json.dumps({"retrieval_evidence": evidence.model_dump(mode="json")})


__all__ = ["TableCatalogRetrievalTool"]
