import os
import sys
import logging
from langchain_core.tools import BaseTool
from typing import Optional, Dict, Literal, Union
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import ConfigDict, BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.geography_registry import GeographyRegistry
from src.tools.geography_schemas import GeographyEnumerationInput, ListLevelsInput, GeographyLevel

logger = logging.getLogger(__name__)

class GeographyDiscoveryInput(BaseModel):
    """Input for geography discovery - supports enumerate and list_levels"""
    action: Literal["enumerate_areas", "list_levels"] = Field(..., description="Action to perform")
    level: Optional[GeographyLevel] = Field(default=None, description="Geography level (required for enumerate)")
    dataset: str = Field(default="acs/acs5", description="A census dataset is a collection of statistical information gathered from every individual or household in a specific region, used for demographic, social, and economic analysis")
    year: int = Field(default=2023, description="Census year which is the year of the data you want to analyze")
    parent: Optional[Dict[str, str]] = Field(default=None, description="Parent geography constraint")

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

    def _run(self, tool_input: str) -> str:
        """Execute geography discovery action
        
        Accepts JSON string input from ReAct agent
        """
        import json
        
        # Parse JSON input
        try:
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
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
        
        registry = GeographyRegistry()
        
        if action == "list_levels":
            # Return all available geography levels
            levels = [lvl.value for lvl in GeographyLevel]
            return json.dumps({
                "dataset": dataset,
                "year": year,
                "available_levels": levels,
                "note": "These are common Census geography levels. Check geography.html for dataset-specific availability."
            })
        
        elif action == "enumerate_areas":
            if level is None:
                return "Error: 'level' is required for enumerate_areas action"
            
            # Handle GeographyLevel enum
            if isinstance(level, GeographyLevel):
                geo_token = level.value
            else:
                geo_token = level
            
            logger.info(f"Enumerating: {geo_token} (parent: {parent})")
            
            areas = registry.enumerate_areas(
                dataset=dataset,
                year=year,
                geo_token=geo_token,
                parent_geo=parent
            )
            
            if not areas:
                return f"No areas found for {geo_token}"
            
            return json.dumps({
                "level": geo_token,
                "count": len(areas),
                "areas": areas
            })
        
        else:
            return f"Unknown action: {action}"
