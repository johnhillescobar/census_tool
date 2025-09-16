from typing import Dict, Any
from src.state.types import CensusState

import logging
from config import RETRIEVAL_TOP_K

from langchain_core.runnables import RunnableConfig

from src.utils.chroma_utils import initialize_chroma_client, get_chroma_collection
from src.utils.retrieval_utils import process_chroma_results, get_fallback_candidates

from src.utils.text_utils import build_retrieval_query


logger = logging.getLogger(__name__)


def plan_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Plan the Census data retrieval"""

    # TODO: Implement plan node

    return {"logs": ["plan: placeholder"]}


def retrieve_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Retrieve the Census data"""

    # Get state
    intent = state.get("intent", {})
    profile = state.get("profile", {})

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
