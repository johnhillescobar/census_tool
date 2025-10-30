import os
import sys
import logging
import json
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.census_api_utils import fetch_census_data


logger = logging.getLogger(__name__)


class CensusAPITool(BaseTool):
    """Execute Census API queries and fetch data"""

    name: str = "census_api_call"
    description: str = """
    Execute a Census API query and fetch actual data.
    
    Supports complex Census API patterns including:
    - Multiple dataset categories (acs/acs5, acs/acs5/subject, acs/acs1/profile, etc.)
    - Complex geography hierarchies (CBSAs, Metropolitan Divisions, NECTAs)
    - Group syntax for subject tables (group(S0101))
    - Multi-level geography constraints with chained in= clauses
    
    Input must be valid JSON with these fields:
    - year: Census year (required)
    - dataset: Dataset path like "acs/acs5", "acs/acs5/subject", "acs/acs1/profile" (required)
    - variables: List of variable codes OR "group(TABLE_CODE)" for subject tables (required)
    - geo_for: Geography for clause dict like {"county": "*", "state (or part)": "*"} (required)
    - geo_in: Geography in clause dict(s) - can be complex like {"state": "06", "metropolitan statistical area/micropolitan statistical area": "35620"} (optional)
    - geo_in_chained: For complex nested queries, array of geo_in objects to chain together (optional)
    
    Examples:
    - Simple: {"year": 2023, "dataset": "acs/acs5", "variables": ["NAME", "B01003_001E"], "geo_for": {"county": "*"}, "geo_in": {"state": "06"}}
    - Subject table: {"year": 2023, "dataset": "acs/acs5/subject", "variables": ["group(S0101)"], "geo_for": {"state": "*"}}
    - Complex CBSA: {"year": 2023, "dataset": "acs/acs5", "variables": ["NAME", "B01001_001E"], "geo_for": {"state (or part)": "*"}, "geo_in": {"metropolitan statistical area/micropolitan statistical area": "35620", "metropolitan division": "35614"}}
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        """Execute Census API query and fetch data"""
        # Parse JSON input
        try:
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
            else:
                params = tool_input
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input - {e}"

        # Extract parameters
        year = params.get("year")
        dataset = params.get("dataset")
        variables = params.get("variables")
        geo_for = params.get("geo_for")
        geo_in = params.get("geo_in")
        geo_in_chained = params.get("geo_in_chained", [])

        if not all([year, dataset, variables, geo_for]):
            return (
                "Error: Missing required parameters (year, dataset, variables, geo_for)"
            )

        logger.info(f"Fetching Census data: {dataset}/{year}")

        try:
            # Build geo parameter in the correct format for fetch_census_data
            geo_filters = {}

            # Convert geo_for dict to Census API format - handle complex cases
            if geo_for:
                for_clauses = []
                for key, value in geo_for.items():
                    for_clauses.append(f"{key}:{value}")
                geo_filters["for"] = " ".join(for_clauses)

            # Handle complex geo_in cases - support chained in= clauses
            in_clauses = []

            # Standard geo_in dict
            if geo_in:
                for key, value in geo_in.items():
                    in_clauses.append(f"{key}:{value}")

            # Handle chained geo_in for complex hierarchies (e.g., state within CBSA within division)
            if geo_in_chained and isinstance(geo_in_chained, list):
                for in_dict in geo_in_chained:
                    if isinstance(in_dict, dict):
                        for key, value in in_dict.items():
                            in_clauses.append(f"{key}:{value}")

            if in_clauses:
                geo_filters["in"] = " ".join(in_clauses)

            geo_params = {"filters": geo_filters}

            result = fetch_census_data(
                dataset=dataset, year=year, variables=variables, geo=geo_params
            )

            logger.info(f"Census data fetched successfully: {result}")
            return json.dumps(
                {
                    "success": True,
                    "row_count": len(result) if result else 0,
                    "data": result,
                }
            )

        except Exception as e:
            logger.error(f"Census API error: {e}")
            return json.dumps({"success": False, "error": str(e)})
