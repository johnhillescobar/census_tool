"""
Retrieval and scoring utilities for Census TABLES (not variables)
This is the table-level version of retrieval_utils.py
"""
import logging
from typing import Dict, Any, List
from config import CONFIDENCE_THRESHOLD


logger = logging.getLogger(__name__)

def process_chroma_results_tables(
    results: Dict, measures: List[str], time_info: Dict, preferred_dataset: str) -> Dict[str, Any]:
    """
    Process ChromaDB results for TABLE-level search
    
    Similar to process_chroma_results() in retrieval_utils.py,
    but works with table metadata instead of variable metadata
    
    Args:
        results: ChromaDB query results with table documents
        measures: User's requested measures (e.g., ["population"])
        time_info: Time range requested
        preferred_dataset: Preferred Census dataset
        
    Returns:
        Dict with "tables" list (not "variables")
    """

    tables = []
    requested_years = set()

    # Extract requested years (same logic as variables)
    if "year" in time_info:
        requested_years.add(time_info["year"])
    elif "start_year" in time_info and "end_year" in time_info:
        requested_years.update(
            range(time_info["start_year"], time_info["end_year"] + 1)
        )

    # Process each table result from ChromaDB
    for doc, metadata, distance in zip(
        results["documents"][0], 
        results["metadatas"][0], 
        results["distances"][0]
    ):
        base_score = 1.0 - distance

        # Score this table
        final_score = calculate_table_confidence_score(
            base_score, metadata, measures, preferred_dataset
        )

        # Parse years available for this table
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

        # Build table info dict
        table = {
            "table_code": metadata.get("table_code", ""),
            "table_name": metadata.get("table_name", ""),
            "description": metadata.get("description", ""),
            "dataset": metadata.get("dataset", ""),
            "data_types": metadata.get("data_types", "").split(",") if metadata.get("data_types") else [],
            "years_available": years_available,
            "score": final_score,
        }
        
        tables.append(table)  # Add table to list!

    # Sort by score (highest first) - OUTSIDE the loop
    tables.sort(key=lambda x: x["score"], reverse=True)

    # Determine years to use (same logic as variables) - OUTSIDE the loop
    if requested_years and tables:
        available_years = set()
        for table in tables:
            available_years.update(table["years_available"])
        years_to_use = sorted(list(requested_years.intersection(available_years)))
    elif tables:
        # Use most recent available year
        all_years = set()
        for table in tables:
            all_years.update(table["years_available"])
        years_to_use = [max(all_years)] if all_years else []
    else:
        years_to_use = []

    return {
        "tables": tables,
        "years": years_to_use,
        "notes": f"Retrieved {len(tables)} candidates for measures: {measures}",
    }


def calculate_table_confidence_score(
    base_score: float, metadata: Dict, measures: List[str], preferred_dataset: str) -> float:
    """
    Calculate confidence score for table matches
    
    Similar to calculate_confidence_score() in retrieval_utils.py,
    but uses table-level metadata (table_name, data_types)
    instead of variable-level metadata (label, concept, var code)
    """
    boost = 0.0

    # Boost for tables WITHOUT race suffixes (general tables)
    logger.info(f"Boosting table {metadata.get('table_code', '')} without race suffix")
    table_code = metadata.get("table_code", "")
    if table_code and not table_code[-1].isalpha():  # No letter at end
        boost += 0.20  # Prefer B19013 over B19013A

    # Boost commonly-used core tables
    CORE_TABLES = {
        "B01003": 0.15,  # Total Population
        "B19013": 0.15,  # Median Household Income
        "B25003": 0.15,  # Tenure (owner/renter)
        "B17001": 0.10,  # Poverty Status
        "B01002": 0.10,  # Median Age
        "B25001": 0.10,  # Total Housing Units
    }
    if table_code in CORE_TABLES:
        boost += CORE_TABLES[table_code]

    # GEt table metadata fields
    table_name = metadata.get("table_name", "").lower()
    data_types = metadata.get("data_types", "")

    # Boost for exact keyword matches in measures
    for measure in measures:
        if measure.lower() in table_name:
            boost += 0.15
            break
    
    # Boost for data type matches
    for measure in measures:
        if measure.lower() in data_types:
            boost += 0.1
            break
    
    # Boost for preferred dataset
    if metadata.get("dataset") == preferred_dataset:
        boost += 0.05

    return min(1.0, base_score + boost)
        

def search_tables_chroma(collection: Any, query: str, k: int = 10, dataset_filter: str = None) -> List[Dict]:
    """Search ChromaDB for tables matching query"""

    results = collection.query(query_texts=[query], n_results=k)

    processed_results = process_chroma_results_tables(
        results, 
        measures = [], 
        time_info = {}, 
        preferred_dataset = dataset_filter)

    return processed_results["tables"]