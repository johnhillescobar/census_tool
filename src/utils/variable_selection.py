"""
Variable selection from Census tables
After finding the right table, select appropriate variables from it
"""

import sys
from pathlib import Path
from typing import List
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.census_groups import CensusGroupsAPI

logger = logging.getLogger(__name__)


def select_variables_from_table(
    table_code: str, dataset: str, year: int, measures: List[str]
) -> List[str]:
    """
    Select appropriate variables from a Census table

    This is the NEW step in the table-level flow:
    1. ChromaDB finds table B01003
    2. This function fetches variables for B01003
    3. This function selects the right ones (e.g., B01003_001E)
    4. Returns them in variable format for downstream processing

    Args:
        table_code: Census table code (e.g., "B01003")
        dataset: Dataset path (e.g., "acs/acs5")
        year: Year to fetch (e.g., 2023)
        measures: User's requested measures (for future smart selection)

    Returns:
        List of variable dicts with keys: var, label, concept, table_code
    """

    api = CensusGroupsAPI()

    # Fetch detailed variables for this table
    table_details = api.fetch_group_details(dataset, year, table_code)

    if not table_details:
        logger.warning(f"Could not fetch details for table {table_code}")
        return []

    if "variables" not in table_details:
        logger.warning(f"No variables found for table {table_code}")
        return []

    # Filter and select variables
    selected_variables = []

    for var_code, var_info in table_details["variables"].items():
        # FILTER 1: Skip metadata variables
        if var_code in ["NAME", "GEO_ID", "for", "in"]:
            continue

        # FILTER 2: Only keep estimate variables (end with 'E')
        # Skip margin of error ('M'), annotation ('MA'), etc.
        if not var_code.endswith("E"):
            continue

        # FILTER 3: For simple queries, prefer the main total (_001E)
        # This is where you'll add more sophisticated logic later
        # For now, just take the first estimate variable

        selected_variables.append(
            {
                "var": var_code,
                "label": var_info.get("label", ""),
                "concept": var_info.get("concept", ""),
                "dataset": dataset,
                "table_code": table_code,
                "years_available": [year],  # We know this year works
                "score": 0.9,  # High score since it came from selected table
            }
        )

    # For simplicity: return just the first variable (usually _001E, the total)
    # Later you can add logic to return multiple variables based on measures
    if selected_variables:
        logger.info(
            f"Selected {len(selected_variables[:1])} variables from table {table_code}"
        )
        return selected_variables[:1]

    logger.warning(f"No suitable variables found in table {table_code}")
    return []
