import os
import sys
import logging
import json
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.census_api_utils import fetch_census_data, build_geo_filters
from src.utils.telemetry import record_event


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

        def _coerce_geo_dict(raw_value):
            if isinstance(raw_value, dict):
                return raw_value
            if isinstance(raw_value, str):
                clauses = {}
                for clause in raw_value.split():
                    token, _, val = clause.partition(":")
                    if val:
                        clauses[token] = val
                return clauses
            return {}

        try:
            geo_filters = build_geo_filters(
                dataset=dataset,
                year=year,
                geo_for=_coerce_geo_dict(geo_for),
                geo_in=_coerce_geo_dict(geo_in),
                geo_in_chained=geo_in_chained,
            )

            geo_params = {"filters": geo_filters}

            result = fetch_census_data(
                dataset=dataset, year=year, variables=variables, geo=geo_params
            )

            logger.info(f"Census data fetched successfully: {result}")

            record_event(
                "census_api_call",
                {
                    "dataset": dataset,
                    "year": year,
                    "variables": variables,
                    "geo_filters": geo_params["filters"],
                    "success": True,
                    "row_count": len(result) if result else 0,
                },
            )
            return json.dumps(
                {
                    "success": True,
                    "row_count": len(result) if result else 0,
                    "data": result,
                }
            )

        except Exception as e:
            logger.error(f"Census API error: {e}")
            record_event(
                "census_api_call",
                {
                    "dataset": dataset,
                    "year": year,
                    "variables": variables,
                    "success": False,
                    "error": str(e),
                },
            )
            return json.dumps({"success": False, "error": str(e)})
