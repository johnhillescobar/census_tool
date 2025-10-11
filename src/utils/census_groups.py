"""
Census Groups API - Fetch table/group metadata instead of individual variables
This is the foundation for table-level search
"""

import requests
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import (CENSUS_API_TIMEOUT, CENSUS_API_MAX_RETRIES, CENSUS_API_BACKOFF_FACTOR)

logger = logging.getLogger(__name__)


class CensusGroupsAPI:
    """Fetch Census table (group) metadata from the Groups API"""

    def __init__(self):
        self.base_url = "https://api.census.gov/data"

    def fetch_groups_list(self, dataset: str, year: int) -> List[Dict]:
        """
        Fetch list of all available groups/tables for a dataset
        
        Example:
            groups = api.fetch_groups_list("acs/acs5", 2023)
            # Returns: [
            #   {"name": "B01003", "description": "Total Population", ...},
            #   {"name": "B19013", "description": "Median Household Income", ...}
            # ]
        """

        url = f"{self.base_url}/{year}/{dataset}/groups.json"

        try:
            logger.info(f"Fetching groups from {url}")
            response = requests.get(url, timeout=CENSUS_API_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            # The response has a "groups" key with a list of group metadata
            return data.get("groups", [])

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch groups from {url}: {e}")
            return []

    def fetch_group_details(self, dataset: str, year: int, group_code: str) -> Optional[Dict]:
        """
        Fetch detailed metadata for a specific group/table
        
        Example:
            details = api.fetch_group_details("acs/acs5", 2023, "B01003")
            # Returns: {
            #   "name": "B01003",
            #   "description": "Total Population",
            #   "variables": {
            #       "B01003_001E": {"label": "Estimate!!Total", ...}
            #   }
            # }
        """

        url = f"{self.base_url}/{year}/{dataset}/groups/{group_code}.json"

        try:
            logger.info(f"Fetching group details from {url}")
            response = requests.get(url, timeout=CENSUS_API_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            # The response has a "name", "description", "variables" key. Here, variables is a URL pointing to the variables for the group.
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch group details from {url}: {e}")
            return None
        

    def aggregate_groups_across_years(self, dataset: str, years: List[int]) -> List[Dict]:
        """
        Aggregate table/group information across multiple years
        
        This builds a comprehensive view of each table:
        - Which years it's available in
        - What variables it contains
        - What kind of data it represents
        
        Returns:
            {
                "B01003": {
                    "table_code": "B01003",
                    "table_name": "Total Population",
                    "description": "Population counts by geography",
                    "dataset": "acs/acs5",
                    "years_available": [2012, 2013, ..., 2023],
                    "variables": {...},
                    "data_types": ["population", "demographics"]
                },
                ...
            }
        """

        aggregated = {}

        for year in years:
            groups = self.fetch_groups_list(dataset, year)
            for group in groups:
                group_code = group.get("name", "")

                # Initialize if time seeing this group
                if group_code not in aggregated:
                    aggregated[group_code] = {
                        "table_code": group_code,
                        "table_name": group.get("description", ""),
                        "description": group.get("description", ""),
                        "dataset": dataset,
                        "years_available": set(),
                        "variables": {},
                        "data_types": [] # We'll infer this from the table code/name
                    }

                # Add this year to availability
                if year not in aggregated[group_code]["years_available"]:
                    aggregated[group_code]["years_available"].add(year)

                # Optionally fetch detailed variables for this group
                # (You might want to do this selectively to avoid too many API calls)
                # COMMENTED OUT: Too many API calls for initial testing
                # details = self.fetch_group_details(dataset, year, group_code)
                # if details and "variables" in details:
                #     aggregated[group_code]["variables"].update(details["variables"])

        # Sort years in each group (convert set to sorted list)
        for group_code in aggregated:
            aggregated[group_code]["years_available"] = sorted(
                list(aggregated[group_code]["years_available"])
            )

            # Infer data types from table code/name
            aggregated[group_code]["data_types"] = self._infer_data_types(
                group_code, 
                aggregated[group_code]["table_name"]
            )

        return aggregated


    def _infer_data_types(self, table_code: str, table_name: str) -> List[str]:
        """
        Infer what type of data this table contains based on code and name
        
        This helps with semantic search - users asking about "income" should
        find income-related tables
        """
        data_types = []
        table_name_lower = table_name.lower()

        # Population-related
        if any(term in table_name_lower for term in ["population", "people", "residents", "inhabitants"]):
            data_types.append("population")
            data_types.append("demographics")

        # Income-related
        if any(term in table_name_lower for term in ["income", "earnings", "poverty", "economic"]):
            data_types.append("income")
            data_types.append("economics")

        # Housing-related
        if any(term in table_name_lower for term in ["housing", "tenure", "occupancy", "units"]):
            data_types.append("housing")

        # Employment-related
        if any(term in table_name_lower for term in ["employment", "unemployment", "labor force", "working"]):
            data_types.append("employment")

        # Education-related
        if any(term in table_name_lower for term in ["education", "schooling", "college", "degree", "academic"]):
            data_types.append("education")

        # Race-related
        if any(term in table_name_lower for term in ["race", "ethnicity", "demographic", "characteristics"]):
            data_types.append("race_ethnicity")

        return data_types if data_types else ["general"]

# Test function to explore the API
def test_census_groups_api():
    """Test the Groups API to see what data is available"""

    api = CensusGroupsAPI()

    # Test 1: Get all groups for ACS 5-year 2023
    print("=" * 60)
    print("TEST 1: Fetching all groups for acs/acs5 2023")
    print("=" * 60)
    groups = api.fetch_groups_list("acs/acs5", 2023)
    print(f"Found {len(groups)} groups/tables")
    print("\nFirst 5 groups:")
    for i, group in enumerate(groups[:5]):
        print(f"  {i+1}. {group.get('name')}: {group.get('description')}")
    
    # Test 2: Get details for specific table
    print("\n" + "=" * 60)
    print("TEST 2: Fetching details for B01003 (Total Population)")
    print("=" * 60)
    details = api.fetch_group_details("acs/acs5", 2023, "B01003")
    if details:
        print(f"Name: {details.get('name')}")
        print(f"Description: {details.get('description')}")
        print(f"Variables in this table:")
        for var_code, var_info in list(details.get('variables', {}).items())[:3]:
            print(f"  - {var_code}: {var_info.get('label')}")
    
    # Test 3: Aggregate across years
    print("\n" + "=" * 60)
    print("TEST 3: Aggregating groups across years 2021-2023")
    print("=" * 60)
    aggregated = api.aggregate_groups_across_years("acs/acs5", [2021, 2022, 2023])
    print(f"Total unique tables: {len(aggregated)}")
    
    # Show population table
    if "B01003" in aggregated:
        print("\nB01003 table info:")
        for key, value in aggregated["B01003"].items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    test_census_groups_api()
                
            