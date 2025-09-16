"""
Retrieval and scoring utilities for Census variables
"""

from typing import Dict, List, Any, Optional
from config import CONFIDENCE_THRESHOLD, VARIABLE_FALLBACKS


def process_chroma_results(
    results: Dict, measures: List[str], time_info: Dict, preferred_dataset: str
) -> Dict[str, Any]:
    """Process Chroma results and apply scoring/filtering"""
    variables = []
    requested_years = set()

    # Extract requested years
    if "year" in time_info:
        requested_years.add(time_info["year"])
    elif "start_year" in time_info and "end_year" in time_info:
        requested_years.update(
            range(time_info["start_year"], time_info["end_year"] + 1)
        )

    # Process each result
    for i, (doc, metadata, distance) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        # Calculate confidence score (1 - distance, since lower distance = higher similarity)
        base_score = 1.0 - distance

        # Apply scoring boosts using the dedicated function
        final_score = calculate_confidence_score(
            base_score, metadata, measures, preferred_dataset
        )

        # Parse years available
        years_available = []
        if metadata.get("years_available"):
            years_str = metadata["years_available"]
            try:
                years_available = [
                    int(y.strip()) for y in years_str.split(",") if y.strip()
                ]
            except ValueError:
                years_available = []

        # Filter by years if requested
        if requested_years:
            available_years = set(years_available)
            if not requested_years.intersection(available_years):
                continue  # Skip if no year overlap

        variable = {
            "var": metadata.get("var", ""),
            "label": metadata.get("label", ""),
            "concept": metadata.get("concept", ""),
            "universe": metadata.get("universe", ""),
            "dataset": metadata.get("dataset", ""),
            "years_available": years_available,
            "score": final_score,
        }

        variables.append(variable)

    # Sort by score (highest first)
    variables.sort(key=lambda x: x["score"], reverse=True)

    # Determine years to use
    if requested_years and variables:
        # Use intersection of requested and available
        available_years = set()
        for var in variables:
            available_years.update(var["years_available"])
        years_to_use = sorted(list(requested_years.intersection(available_years)))
    elif variables:
        # Use most recent available year
        all_years = set()
        for var in variables:
            all_years.update(var["years_available"])
        years_to_use = [max(all_years)] if all_years else []
    else:
        years_to_use = []

    return {
        "variables": variables,
        "years": years_to_use,
        "notes": f"Retrieved {len(variables)} candidates for measures: {measures}",
    }


def calculate_confidence_score(
    base_score: float, metadata: Dict, measures: List[str], preferred_dataset: str
) -> float:
    """Calculate confidence score with boosts"""
    boost = 0.0

    # Get metadata fields
    label = metadata.get("label", "").lower()
    concept = metadata.get("concept", "").lower()
    var_code = metadata.get("var", "")

    # Boost for exact keyword matches in measures
    for measure in measures:
        if measure.lower() in label or measure.lower() in concept:
            boost += 0.1
            break  # Only boost once for any measure match

    # Boost for specific important terms
    if "population" in label and "total" in label:
        boost += 0.05
    if "median" in label:
        boost += 0.05
    if "hispanic" in label or "latino" in label:
        boost += 0.05

    # Boost for main estimate variables (_001E)
    if var_code.endswith("_001E"):
        boost += 0.1

    # Boost for preferred dataset
    if metadata.get("dataset") == preferred_dataset:
        boost += 0.05

    # Ensure score doesn't exceed 1.0
    final_score = min(1.0, base_score + boost)

    return final_score


def get_fallback_candidates(
    measures: List[str], preferred_dataset: str
) -> Optional[Dict[str, Any]]:
    """Get fallback candidates when Chroma search fails"""
    fallback_vars = []

    # Check for direct fallback matches
    measures_text = " ".join(measures).lower()

    for measure_key, var_code in VARIABLE_FALLBACKS.items():
        if measure_key in measures_text:
            fallback_vars.append(
                {
                    "var": var_code,
                    "label": f"fallback for {measure_key}",
                    "concept": f"fallback for {measure_key}",
                    "universe": "All",
                    "dataset": preferred_dataset,
                    "years_available": [2023],
                    "score": CONFIDENCE_THRESHOLD - 0.2,
                }
            )

    if fallback_vars:
        return {
            "variables": fallback_vars,
            "years": [2023],
            "notes": f"Used fallback variables for: {measures_text}",
        }

    return None
