import os
import sys
import logging
from langchain_core.tools import BaseTool
import requests
import json
from typing import Optional
from pydantic import ConfigDict

logger = logging.getLogger(__name__)


class TableValidationTool(BaseTool):
    """
    Validate table supports requested geography
    """

    name: str = "validate_table_geography"
    description: str = """
    Check if a Census table supports a specific geography level.

    Input must be valid JSON:
    - table_code: Table code like "B01003" (required)
    - geography_level: Level like "county" (required)
    - dataset: Dataset like "acs/acs5" (optional)

    Examples:
    - {"table_code": "B01003", "geography_level": "county"}
    - {"table_code": "S0101", "geography_level": "tract", "dataset": "acs/acs5"}
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        """Validate table supports geography level"""

        # Parse JSON input
        try:
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
            else:
                params = tool_input
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input - {e}"

        # Extract parameters
        table_code = params.get("table_code")
        geography_level = params.get("geography_level")
        dataset = params.get("dataset", "acs/acs5")

        if not all([table_code, geography_level]):
            return "Error: Missing required parameters (table_code, geography_level)"

        logger.info(f"Validating {table_code} for {geography_level}")

        # Stub: Assume common tables support common geographies
        # TODO: Query actual geography.html for real validation
        common_geographies = [
            "nation",
            "state",
            "county",
            "place",
            "tract",
            "block group",
        ]

        supported = geography_level in common_geographies

        return json.dumps(
            {
                "table_code": table_code,
                "geography_level": geography_level,
                "dataset": dataset,
                "supported": supported,
                "available_geographies": common_geographies,
                "note": "Stub validation - assumes common tables support common geographies",
            }
        )
