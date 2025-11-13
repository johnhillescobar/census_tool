import os
import sys
import logging
from langchain_core.tools import BaseTool
import json
from pydantic import ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.census_api_utils import build_geo_filters

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
            # User/agent specified exact variables - use them
            variables = (
                custom_variables
                if isinstance(custom_variables, list)
                else [custom_variables]
            )
        elif use_groups is True:
            # Explicit group request
            variables = [f"group({table_code})"]
            logger.warning(
                f"Using group({table_code}) - will fetch ALL variables from this table. "
                f"Consider specifying only needed variables for better performance."
            )
        elif use_groups is False:
            # Explicit no-group request
            variables = ["NAME", f"{table_code}_001E"]
        else:
            # Auto-detect: Only use groups for small tables or explicit need
            # For profile/subject/cprofile, default to specific variables unless overridden
            if table_category in ["subject", "profile", "cprofile", "spp"]:
                logger.warning(
                    f"Auto-using group() for {table_category} table {table_code}. "
                    f"This may fetch 100+ variables. Consider specifying variables parameter "
                    f"with only needed variables for faster responses."
                )
                variables = [f"group({table_code})"]
            else:
                # Default detail table variables
                variables = ["NAME", f"{table_code}_001E"]

        # Format variables parameter
        if isinstance(variables, list):
            variables_str = ",".join(variables)
        else:
            variables_str = variables

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

        geo_filters = build_geo_filters(
            dataset=dataset,
            year=year,
            geo_for=_coerce_geo_dict(geo_for),
            geo_in=_coerce_geo_dict(geo_in),
        )

        for_param = geo_filters["for"]
        in_param = geo_filters.get("in")

        url = f"{base_url}?get={variables_str}&for={for_param}"
        if in_param:
            url += f"&in={in_param}"

        logger.info(f"Built Census URL: {url}")

        return json.dumps(
            {
                "url": url,
                "base_url": base_url,
                "variables": variables_str,
                "geo_for": for_param,
                "geo_in": in_param,
                "table_category": table_category,
                "use_groups": use_groups
                or table_category in ["subject", "profile", "cprofile", "spp"],
            }
        )
