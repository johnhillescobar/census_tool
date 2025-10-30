import os
import sys
import logging
from langchain_core.tools import BaseTool
import json
from pydantic import ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


logger = logging.getLogger(__name__)


class PatternBuilderTool(BaseTool):
    """
    Construct Census API URL patterns
    """

    name: str = "build_census_url"
    description: str = """
    Build a Census API URL from components with support for complex Census API patterns.
    
    Supports all dataset categories and complex geography hierarchies from CENSUS_DISCUSSION.md:
    - Detail tables (B01003), Subject tables (S0101), Profile tables (DP03)
    - Complex geography hierarchies (CBSAs, Metropolitan Divisions, NECTAs)
    - Group syntax for subject tables and multi-level geo constraints

    Input must be valid JSON:
    - year: Census year (required)
    - dataset: Dataset like "acs/acs5", "acs/acs5/subject", "acs/acs1/profile" (required)
    - table_code: Table code like "B01003", "S0101", "DP03" (required)
    - table_category: "detail", "subject", "profile", "cprofile", "spp" (optional)
    - geo_for: Geography for clause like "county:*" or complex {"county": "*", "state (or part)": "*"} (required)
    - geo_in: Geography in clause like "state:06" or complex multi-level dict (optional)
    - use_groups: Boolean - use group(table_code) syntax for subject/profile tables (optional, auto-detected)
    - variables: Override default variables with custom list (optional)

    Examples:
    - {"year": 2023, "dataset": "acs/acs5", "table_code": "B01003", "geo_for": "county:*", "geo_in": "state:06"}
    - {"year": 2023, "dataset": "acs/acs5/subject", "table_code": "S0101", "geo_for": "state:*", "use_groups": true}
    - {"year": 2023, "dataset": "acs/acs5", "table_code": "B01001", "geo_for": {"state (or part)": "*"}, "geo_in": {"metropolitan statistical area/micropolitan statistical area": "35620"}}
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        """Build Census API URL from components"""

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
        table_code = params.get("table_code")
        table_category = params.get("table_category", "detail")
        geo_for = params.get("geo_for")
        geo_in = params.get("geo_in")
        use_groups = params.get("use_groups", None)
        custom_variables = params.get("variables")

        if not all([year, dataset, table_code, geo_for]):
            return "Error: Missing required parameters (year, dataset, table_code, geo_for)"

        # Build Census API URL
        base_url = f"https://api.census.gov/data/{year}/{dataset}"

        # Determine variable format based on table category and use_groups parameter
        if custom_variables:
            variables = (
                custom_variables
                if isinstance(custom_variables, list)
                else [custom_variables]
            )
        elif use_groups is True or (
            use_groups is None
            and table_category in ["subject", "profile", "cprofile", "spp"]
        ):
            # Use group syntax for subject/profile tables
            variables = [f"group({table_code})"]
        else:
            # Default detail table variables
            variables = ["NAME", f"{table_code}_001E"]

        # Format variables parameter
        if isinstance(variables, list):
            variables_str = ",".join(variables)
        else:
            variables_str = variables

        # Handle complex geo_for - can be string or dict
        if isinstance(geo_for, dict):
            for_clauses = []
            for key, value in geo_for.items():
                for_clauses.append(f"{key}:{value}")
            geo_for_str = " ".join(for_clauses)
        else:
            geo_for_str = geo_for

        # Handle complex geo_in - can be string or dict
        if isinstance(geo_in, dict):
            import urllib.parse

            in_clauses = []
            for key, value in geo_in.items():
                encoded_value = urllib.parse.quote(str(value))
                in_clauses.append(f"{key}:{encoded_value}")
            geo_in_str = " ".join(in_clauses)
        elif geo_in:
            geo_in_str = geo_in
        else:
            geo_in_str = None

        # Build URL with proper encoding for complex geography names
        import urllib.parse

        url = f"{base_url}?get={variables_str}&for={urllib.parse.quote(geo_for_str)}"
        if geo_in_str:
            url += f"&in={urllib.parse.quote(geo_in_str)}"

        logger.info(f"Built Census URL: {url}")

        return json.dumps(
            {
                "url": url,
                "base_url": base_url,
                "variables": variables_str,
                "geo_for": geo_for_str,
                "geo_in": geo_in_str,
                "table_category": table_category,
                "use_groups": use_groups
                or table_category in ["subject", "profile", "cprofile", "spp"],
            }
        )
