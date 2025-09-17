"""
Planning utilities for Census data retrieval
"""

from typing import Dict, Any, List
from src.state.types import QuerySpec
from config import CENSUS_API_VARIABLE_LIMIT


def validate_geo_dataset_compatibility(geo: Dict[str, Any], dataset: str) -> bool:
    """Validate if geography and dataset are compatible"""
    # TODO: Implement this
    return True


def build_query_specs(
    intent: Dict[str, Any],
    geo: Dict[str, Any],
    candidate: Dict[str, Any],
    years: List[int],
) -> List[QuerySpec]:
    """Build query specs for the given intent, geography, candidate, and years"""
    query_specs = []

    for year in years:
        # Always include NAME variable
        variables = [candidate["var"], "NAME"]

        # Enforce variable limit (48 max per call)
        if len(variables) > CENSUS_API_VARIABLE_LIMIT:
            variables = variables[:CENSUS_API_VARIABLE_LIMIT]

        # Create save_as filename
        save_as = f"{candidate['var']}_{geo['level']}_{year}"

        query_spec = QuerySpec(
            year=year,
            dataset=candidate["dataset"],
            variables=variables,
            geo=geo,
            save_as=save_as,
        )
        query_specs.append(query_spec)

    return query_specs
