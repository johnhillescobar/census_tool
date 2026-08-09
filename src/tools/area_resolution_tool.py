import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, Field

from src.domain.geography_catalog import AreaCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis
from src.services.chroma_catalog_retriever import retrieve_geography_candidates
from src.tools.geography_schemas import GeographyLevel
from src.tools.json_parse import parse_first_json

logger = logging.getLogger(__name__)


def _filter_area_candidates(
    area_evidence: RetrievalEvidence,
    *,
    geo_token: str,
    parent: dict[str, str] | None,
) -> list[AreaCandidate]:
    candidates = [
        candidate
        for candidate in area_evidence.candidates
        if isinstance(candidate, AreaCandidate)
        and (candidate.friendly_level == geo_token or candidate.census_token == geo_token)
    ]
    if parent:
        expected_codes = set(parent.values())
        candidates = [
            candidate
            for candidate in candidates
            if not candidate.parent_geo_ids or expected_codes.intersection(candidate.parent_geo_ids)
        ]
    return candidates


def _filtered_area_evidence(
    source: RetrievalEvidence,
    candidates: list[AreaCandidate],
) -> RetrievalEvidence:
    if not candidates:
        return source.model_copy(
            update={
                "status": "empty",
                "candidate_ids": [],
                "candidates": [],
            }
        )
    return source.model_copy(
        update={
            "status": "hit",
            "candidate_ids": [candidate.candidate_id for candidate in candidates],
            "candidates": candidates,
        }
    )


def _area_resolution_payload(
    *,
    status: str,
    area_evidence: RetrievalEvidence,
    hierarchy_evidence: RetrievalEvidence,
    resolved: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "source": "chroma",
        "area_evidence": area_evidence.model_dump(mode="json"),
        "hierarchy_evidence": hierarchy_evidence.model_dump(mode="json"),
    }
    if resolved is not None:
        payload.update(resolved)
    if status == "ambiguous":
        payload["count"] = len(area_evidence.candidates)
    return payload


class AreaResolutionTool(BaseTool):
    """Resolve friendly area names to Census codes"""

    name: str = "resolve_area_name"
    description: str = """
    Resolve a friendly geography name to its Census code.
    
    Use this when you need to convert a single area name to its FIPS code.
    
    Input must be valid JSON with these fields:
    - name: Area name (required)
    - geography_type: Geography level (default: "state")
    - dataset: Census dataset (default: "acs/acs5")
    - year: Year (default: 2023)
    - parent: Parent geography dict (optional)
    
    Returns area_evidence as typed RetrievalEvidence. On an unambiguous hit,
    includes resolved code fields. On ambiguous matches, returns multiple
    candidates in area_evidence for propose_grounded_plan selection.
    
    Examples:
    - {"name": "California", "geography_type": "state"}
    - {"name": "Los Angeles County", "geography_type": "county", "parent": {"state": "06"}}
    """

    # args_schema: type[BaseModel] = AreaResolutionInput  # Disabled for ReAct compatibility
    model_config = ConfigDict(arbitrary_types_allowed=True)
    chroma_client: Any = Field(default=None, exclude=True)

    def _run(self, tool_input: str) -> str:
        """Resolve area name to Census code

        Accepts JSON string input from ReAct agent
        """
        # Parse JSON input
        try:
            if isinstance(tool_input, str):
                params = parse_first_json(tool_input)
            else:
                params = tool_input
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input - {e}"

        # Extract parameters
        name = params.get("name")
        geography_type = params.get("geography_type", "state")
        dataset = params.get("dataset", "acs/acs5")
        year = params.get("year", 2023)
        parent = params.get("parent", None)

        if not name:
            return "Error: 'name' parameter is required"

        # Handle GeographyLevel enum
        if isinstance(geography_type, GeographyLevel):
            geo_token = geography_type.value
        else:
            geo_token = geography_type

        logger.info("Resolving from Chroma: %s (%s)", name, geo_token)
        analysis = CensusRetrievalAnalysis(
            question=name,
            table_search_text="area lookup",
            geography_search_text=geo_token,
            area_search_texts=[name],
            geography_explicit=True,
        )
        retrieved = retrieve_geography_candidates(
            analysis,
            dataset=dataset,
            year=year,
            client=self.chroma_client,
        )
        if not retrieved.area_evidence:
            empty_evidence = RetrievalEvidence(
                evidence_id=f"area-evidence:{name}",
                collection_name="census_geography_areas",
                status="empty",
                query_text=name,
            )
            return json.dumps(
                _area_resolution_payload(
                    status="empty",
                    area_evidence=empty_evidence,
                    hierarchy_evidence=retrieved.hierarchy_evidence,
                )
            )

        source_evidence = retrieved.area_evidence[0]
        candidates = _filter_area_candidates(source_evidence, geo_token=geo_token, parent=parent)
        area_evidence = _filtered_area_evidence(source_evidence, candidates)
        hierarchy_evidence = retrieved.hierarchy_evidence

        if area_evidence.status == "empty":
            logger.info(
                "No Chroma match for '%s' in %s (source_status=%s)",
                name,
                geo_token,
                source_evidence.status,
            )
            return json.dumps(
                _area_resolution_payload(
                    status="empty",
                    area_evidence=area_evidence,
                    hierarchy_evidence=hierarchy_evidence,
                )
            )

        if len(candidates) > 1:
            logger.info(
                "Ambiguous Chroma matches for '%s' in %s (candidates=%s)",
                name,
                geo_token,
                len(candidates),
            )
            return json.dumps(
                _area_resolution_payload(
                    status="ambiguous",
                    area_evidence=area_evidence,
                    hierarchy_evidence=hierarchy_evidence,
                )
            )

        candidate = candidates[0]
        return json.dumps(
            _area_resolution_payload(
                status="resolved",
                area_evidence=area_evidence,
                hierarchy_evidence=hierarchy_evidence,
                resolved={
                    "code": candidate.geography_code,
                    "geo_id": candidate.geo_id,
                    "full_name": candidate.display_name,
                    "geography_type": candidate.friendly_level,
                    "candidate_id": candidate.candidate_id,
                },
            )
        )
