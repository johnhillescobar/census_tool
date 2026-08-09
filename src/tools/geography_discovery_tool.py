import json
import logging
from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis
from src.services.chroma_catalog_retriever import retrieve_geography_candidates
from src.tools.geography_schemas import (
    GeographyLevel,
)
from src.tools.json_parse import parse_first_json

logger = logging.getLogger(__name__)


class GeographyDiscoveryInput(BaseModel):
    """Input for geography discovery - supports enumerate and list_levels"""

    action: Literal["enumerate_areas", "list_levels"] = Field(..., description="Action to perform")
    level: GeographyLevel | None = Field(default=None, description="Geography level (required for enumerate)")
    dataset: str = Field(
        default="acs/acs5",
        description="A census dataset is a collection of statistical information gathered from every individual or household in a specific region, used for demographic, social, and economic analysis",
    )
    year: int = Field(
        default=2023,
        description="Census year which is the year of the data you want to analyze",
    )
    parent: dict[str, str] | None = Field(default=None, description="Parent geography constraint")


class GeographyDiscoveryTool(BaseTool):
    """
    Discover available geography levels and enumerate areas
    """

    name: str = "geography_discovery"
    description: str = """
    Discover available geography levels and enumerate areas.
    
    Input must be valid JSON with these fields:
    - action: "list_levels" or "enumerate_areas" (required)
    - level: Geography level (required for enumerate_areas)
    - dataset: Census dataset (default: "acs/acs5")
    - year: Year (default: 2023)
    - parent: Parent geography dict (optional)
    
    Examples:
    - {"action": "list_levels", "dataset": "acs/acs5", "year": 2023}
    - {"action": "enumerate_areas", "level": "state"}
    - {"action": "enumerate_areas", "level": "county", "parent": {"state": "06"}}
    """

    # args_schema: type[BaseModel] = GeographyDiscoveryInput  # Disabled for ReAct compatibility
    model_config = ConfigDict(arbitrary_types_allowed=True)
    chroma_client: Any = Field(default=None, exclude=True)

    def _run(self, tool_input: str) -> str:
        """Execute geography discovery action

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
        action = params.get("action")
        level = params.get("level", None)
        dataset = params.get("dataset", "acs/acs5")
        year = params.get("year", 2023)
        parent = params.get("parent", None)

        if not action:
            return "Error: 'action' parameter is required"

        if action == "list_levels":
            analysis = CensusRetrievalAnalysis(
                question="available geography levels",
                table_search_text="geography levels",
                geography_search_text="available geography levels",
                geography_explicit=True,
            )
            retrieved = retrieve_geography_candidates(
                analysis,
                dataset=dataset,
                year=year,
                client=self.chroma_client,
            )
            hierarchy = retrieved.hierarchy_evidence
            if hierarchy.status != "hit":
                return json.dumps(
                    {
                        "status": hierarchy.status,
                        "available_levels": [],
                        "source": "chroma",
                        "hierarchy_evidence": hierarchy.model_dump(mode="json"),
                    }
                )
            levels = list(dict.fromkeys(candidate.friendly_level for candidate in hierarchy.candidates))
            return json.dumps(
                {
                    "dataset": dataset,
                    "year": year,
                    "available_levels": levels,
                    "source": "chroma",
                    "hierarchy_evidence": hierarchy.model_dump(mode="json"),
                }
            )

        elif action == "enumerate_areas":
            if level is None:
                return "Error: 'level' is required for enumerate_areas action"

            # Handle GeographyLevel enum
            if isinstance(level, GeographyLevel):
                geo_token = level.value
            else:
                geo_token = level

            logger.info("Enumerating from Chroma: %s (parent: %s)", geo_token, parent)
            query = f"{geo_token} within {parent}" if parent else f"{geo_token} areas"
            analysis = CensusRetrievalAnalysis(
                question=query,
                table_search_text="area enumeration",
                geography_search_text=geo_token,
                area_search_texts=[query],
                geography_explicit=True,
            )
            retrieved = retrieve_geography_candidates(
                analysis,
                dataset=dataset,
                year=year,
                client=self.chroma_client,
            )
            area_evidence = retrieved.area_evidence[0]
            areas = [
                {
                    "candidate_id": candidate.candidate_id,
                    "name": candidate.display_name,
                    "code": candidate.geography_code,
                    "geo_id": candidate.geo_id,
                }
                for candidate in area_evidence.candidates
                if candidate.friendly_level == geo_token or candidate.census_token == geo_token
            ]
            return json.dumps(
                {
                    "status": area_evidence.status,
                    "level": geo_token,
                    "count": len(areas),
                    "areas": areas,
                    "source": "chroma",
                    "hierarchy_evidence": retrieved.hierarchy_evidence.model_dump(mode="json"),
                    "area_evidence": [item.model_dump(mode="json") for item in retrieved.area_evidence],
                }
            )

        else:
            return f"Unknown action: {action}"
