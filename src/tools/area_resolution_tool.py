import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, Field

from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis
from src.services.chroma_catalog_retriever import retrieve_geography_candidates
from src.tools.geography_schemas import GeographyLevel
from src.tools.json_parse import parse_first_json

logger = logging.getLogger(__name__)


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
        area_evidence = retrieved.area_evidence[0]
        candidates = [
            candidate
            for candidate in area_evidence.candidates
            if candidate.friendly_level == geo_token or candidate.census_token == geo_token
        ]
        if parent:
            expected_codes = set(parent.values())
            candidates = [
                candidate
                for candidate in candidates
                if not candidate.parent_geo_ids or expected_codes.intersection(candidate.parent_geo_ids)
            ]
        if area_evidence.status != "hit" or len(candidates) != 1:
            error_msg = (
                f"No unambiguous Chroma match found for '{name}' in {geo_token} "
                f"(status={area_evidence.status}, candidates={len(candidates)})"
            )
            logger.warning(error_msg)
            return error_msg

        candidate = candidates[0]
        return json.dumps(
            {
                "code": candidate.geography_code,
                "geo_id": candidate.geo_id,
                "full_name": candidate.display_name,
                "geography_type": candidate.friendly_level,
                "candidate_id": candidate.candidate_id,
                "source": "chroma",
            }
        )
