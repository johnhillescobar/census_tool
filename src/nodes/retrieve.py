from typing import Dict, Any
from src.state.types import CensusState, QuerySpec

import logging
from config import RETRIEVAL_TOP_K, CONFIDENCE_THRESHOLD

from langchain_core.runnables import RunnableConfig

from src.utils.chroma_utils import (
    initialize_chroma_client,
    get_chroma_collection_tables,
)
from src.utils.retrieval_utils_tables import process_chroma_results_tables
from src.utils.variable_selection import select_variables_from_table
from src.utils.retrieval_utils import process_chroma_results, get_fallback_candidates
from src.utils.planning_utils import (
    validate_geo_dataset_compatibility,
    build_query_specs,
)
from src.utils.text_utils import build_retrieval_query
from src.llm.category_detector import (
    detect_category_with_llm,
    boost_category_results,
    rerank_by_distance,
)


logger = logging.getLogger(__name__)


def plan_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Plan the Census data retrieval"""

    # Get state
    intent = state.intent or {}
    geo = state.geo or {}
    candidates = state.candidates or {}

    if not intent:
        return {
            "error": "No intent found in state",
            "logs": ["plan: ERROR - no intent"],
        }

    if not geo:
        return {
            "error": "No geo found in state",
            "logs": ["plan: ERROR - no geo"],
        }

    if not candidates or not candidates.get("variables"):
        return {
            "error": "No candidates found in state",
            "logs": ["plan: ERROR - no candidates"],
        }

    # Select the best candidate by highest score
    variables = candidates["variables"]
    best_candidate = variables[0]

    # Check confidence threshold
    if best_candidate["score"] < CONFIDENCE_THRESHOLD:
        return {
            "error": "Best candidate score below threshold",
            "logs": [f"plan: confidence {best_candidate['score']:.2f} below threshold"],
        }

    # Validate geo-dataset compatibility
    if not validate_geo_dataset_compatibility(geo, best_candidate["dataset"]):
        return {
            "error": "Geo-dataset compatibility validation failed",
            "logs": [
                f"plan: ERROR - geo-dataset compatibility validation failed for {best_candidate['dataset']}"
            ],
        }

    # Build QuerySpec items
    query_specs = build_query_specs(intent, geo, best_candidate, candidates["years"])

    return {
        "plan": {
            "queries": query_specs,
            "needs_agg": False,
            "agg_spec": None,
        },
        "logs": [f"plan: built {len(query_specs)} query specs"],
    }


def retrieve_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Retrieve the Census data"""

    # Get state
    intent = state.intent or {}
    profile = state.profile or {}

    if not intent:
        return {
            "error": "No intent found in state",
            "logs": ["retrieve: ERROR - no intent"],
        }

    # Build the retrieval query
    query_string = build_retrieval_query(intent, profile)

    # INTEGRATION 2: Detect category preference with LLM
    original_text = intent.get("original_text", query_string)
    category_result = detect_category_with_llm(original_text)
    preferred_category = category_result.get("preferred_category")
    category_confidence = category_result.get("confidence", 0.0)

    logger.info(
        f"Category detection: {preferred_category} (confidence: {category_confidence:.2f})"
    )

    # Get Chroma collection
    client = initialize_chroma_client()
    collection = get_chroma_collection_tables(client)

    # Query ChromaDB
    results = collection.query(query_texts=[query_string], n_results=RETRIEVAL_TOP_K)

    # INTEGRATION 2: Boost category-matching results
    if preferred_category and category_confidence > 0.5:
        logger.info(f"Boosting results for category: {preferred_category}")
        results = boost_category_results(
            results, preferred_category, category_confidence
        )
        results = rerank_by_distance(results)

    if not results["documents"] or not results["documents"][0]:
        fallback = get_fallback_candidates(
            intent.get("measures", []), profile.get("preferred_dataset", "acs/acs5")
        )

        if fallback:
            return {
                "candidates": fallback,
                "logs": ["retrieve: used fallback"],
            }
        return {
            "error": "No candidates found",
            "logs": ["retrieve: ERROR - no candidates"],
        }

    # Process tables results (not variable results)
    table_candidates = process_chroma_results_tables(
        results,
        intent.get("measures", []),
        intent.get("time", {}),
        profile.get("preferred_dataset", "acs/acs5"),
    )

    # Get the best table
    tables = table_candidates.get("tables", [])
    if not tables:
        return {
            "error": "No tables found",
            "logs": ["retrieve: ERROR - no tables found"],
        }

    best_table = tables[0]  # Highest score table
    years = table_candidates.get("years", [])
    year_to_use = years[0] if years else 2023

    # Select variables from the best table
    selected_variables = select_variables_from_table(
        best_table["table_code"],
        best_table["dataset"],
        year_to_use,
        intent.get("measures", []),
    )

    if not selected_variables:
        return {
            "error": f"No variables found in table {best_table['table_code']}",
            "logs": ["retrieve: ERROR - variable selection failed"],
        }

    # Convert back to format expected by plan_node (which expects variables)
    candidates = {
        "variables": selected_variables,
        "years": [year_to_use],
        "notes": f"Selected from table {best_table['table_code']}",
    }

    return {
        "candidates": candidates,
        "logs": [
            f"retrieve: found table {best_table['table_code']} (score: {best_table['score']:.2f})",
            f"retrieve: selected {len(selected_variables)} variables",
        ],
    }
