from typing import Dict, Any
from src.state.types import CensusState, QuerySpec

import logging
from config import RETRIEVAL_TOP_K, CONFIDENCE_THRESHOLD

from langchain_core.runnables import RunnableConfig

from src.utils.chroma_utils import initialize_chroma_client, get_chroma_collection
from src.utils.retrieval_utils import process_chroma_results, get_fallback_candidates
from src.utils.planning_utils import (
    validate_geo_dataset_compatibility,
    build_query_specs,
)
from src.utils.text_utils import build_retrieval_query


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

    # Get Chroma collection
    client = initialize_chroma_client()
    collection = get_chroma_collection(client)

    # Query and process results
    results = collection.query(query_texts=[query_string], n_results=RETRIEVAL_TOP_K)

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

    # Process results
    candidates = process_chroma_results(
        results,
        intent.get("measures", []),
        intent.get("time", {}),
        profile.get("preferred_dataset", "acs/acs5"),
    )

    variable_count = len(candidates.get("variables", []))
    return {
        "candidates": candidates,
        "logs": [f"retrieve: found {variable_count} candidates"],
    }
