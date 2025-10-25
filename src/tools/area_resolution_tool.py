import os
import sys
import logging
import json
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.geography_registry import GeographyRegistry
from src.tools.geography_schemas import GeographyLevel


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

    def _run(self, tool_input: str) -> str:
        """Resolve area name to Census code

        Accepts JSON string input from ReAct agent
        """
        # Parse JSON input
        try:
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
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

        logger.info(f"Resolving: {name} ({geo_token})")
        registry = GeographyRegistry()

        result = registry.find_area_code(
            friendly_name=name,
            geo_token=geo_token,
            dataset=dataset,
            year=year,
            parent_geo=parent,
        )

        if result is None:
            error_msg = f"No match found for '{name}' in {geo_token}"
            logger.warning(error_msg)
            return error_msg

        return json.dumps(result)
