"""
Chroma database utilities for Census variable retrieval
"""

import json
import logging
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

import chromadb
from chromadb.config import Settings

from config import (
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_COLLECTION_NAME,
    CHROMA_TABLE_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
)

logger = logging.getLogger(__name__)

_GEO_TOKEN_CANONICAL = {
    "nation": "us",
    "cbsa": "metropolitan statistical area/micropolitan statistical area",
    "msa": "metropolitan statistical area/micropolitan statistical area",
    "metropolitan statistical area": "metropolitan statistical area/micropolitan statistical area",
    "micropolitan statistical area": "metropolitan statistical area/micropolitan statistical area",
}


def initialize_chroma_client() -> chromadb.PersistentClient:
    """Initialize and return Chroma client"""
    try:
        client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
        )

    except Exception as e:
        logger.error(f"Failed to connect to Chroma: {e}")
        return {
            "error": f"Failed to connect to variable database: {e}",
            "logs": ["retrieve: ERROR - Chroma connection failed"],
        }

    return client


def get_chroma_collection_variables(
    client: chromadb.PersistentClient,
) -> chromadb.Collection:
    """Get the census variables collection"""
    # Implementation here
    try:
        collection = client.get_collection(CHROMA_COLLECTION_NAME)
    except Exception as e:
        logger.error(f"Failed to get Chroma collection: {e}")
        return {
            "error": f"Failed to get Chroma collection: {e}",
            "logs": ["retrieve: ERROR - Chroma collection not found"],
        }
    return collection


def get_chroma_collection_tables(
    client: chromadb.PersistentClient,
) -> chromadb.Collection:
    """Get the census tables collection"""
    try:
        collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
    except Exception as e:
        logger.error(f"Failed to get Chroma collection: {e}")
        return {
            "error": f"Failed to get Chroma collection: {e}",
            "logs": ["retrieve: ERROR - Chroma collection not found"],
        }
    return collection


def _normalize_geo_token(token: str) -> str:
    if not token:
        return token
    key = token.strip().lower()
    return _GEO_TOKEN_CANONICAL.get(key, token.strip())


@lru_cache(maxsize=512)
def get_hierarchy_ordering(dataset: str, year: int, for_level: str) -> List[str]:
    """
    Return the expected parent ordering for `for_level` given dataset/year.
    Looks up the census_geography_hierarchies Chroma collection.
    Falls back to [] when no ordering is found.
    """
    client = initialize_chroma_client()
    if isinstance(client, dict):  # error payload from initialize_chroma_client
        logger.error("Could not initialize Chroma client for hierarchy lookup")
        return []

    try:
        collection = client.get_collection(CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME)
        result = collection.get(
            where={
                "$and": [
                    {"dataset": {"$eq": dataset}},
                    {"year": {"$eq": year}},
                    {"for_level": {"$eq": for_level}},
                ]
            },
            include=["metadatas"],
        )
    except Exception as exc:
        logger.error("Hierarchy lookup failed: %s", exc)
        return []

    metadatas = result.get("metadatas") or []
    if not metadatas:
        return []

    # Use the first match; ordering_list is stored as JSON string.
    ordering_json = metadatas[0].get("ordering_list")
    if not ordering_json:
        return []

    try:
        ordering = json.loads(ordering_json)
    except json.JSONDecodeError:
        return []

    return [_normalize_geo_token(token) for token in ordering]


def validate_and_fix_geo_params(
    dataset: str,
    year: int,
    geo_for: Dict[str, str],
    geo_in: Optional[Dict[str, str]] = None,
    *,
    extra_in: Optional[Iterable[Tuple[str, str]]] = None,
    validate_completeness: bool = False,
) -> Tuple[str, str, List[Tuple[str, str]]]:
    """
    Normalize geo_for/geo_in into a canonical (for_token, for_value, ordered_in list).

    - Ensures only one geography level remains in `for`.
    - Moves parent levels from geo_for into the `in` set.
    - Applies hierarchy ordering from the geography collection.
    - Performs token normalization (nation→us, cbsa→metropolitan statistical area/micropolitan statistical area, etc.)
    - Optionally validates that all required parent geographies are provided.

    Args:
        dataset: Census dataset path
        year: Census year
        geo_for: Geography for clause
        geo_in: Geography in clause (optional)
        extra_in: Additional in clauses (optional)
        validate_completeness: If True, raise ValueError if required parent geographies are missing

    Returns:
        Tuple of (for_token, for_value, ordered_in_list)

    Raises:
        ValueError: If geo_for is empty or if validate_completeness=True and required parents are missing
    """
    if not geo_for:
        raise ValueError("geo_for is required")

    normalized_for_items = [
        (_normalize_geo_token(k), str(v).strip()) for k, v in geo_for.items()
    ]
    # target level is the most granular entry (last given)
    for_token, for_value = normalized_for_items[-1]
    parent_pairs = normalized_for_items[:-1]

    normalized_in = []
    if geo_in:
        normalized_in.extend(
            (_normalize_geo_token(k), str(v).strip()) for k, v in geo_in.items()
        )
    if extra_in:
        normalized_in.extend(
            (_normalize_geo_token(k), str(v).strip()) for k, v in extra_in
        )
    # Add parents we removed from geo_for
    normalized_in.extend(parent_pairs)

    # Determine ordering
    ordering = get_hierarchy_ordering(dataset, year, for_token) or [
        token for token, _ in normalized_in
    ]
    ordering_index = {token: idx for idx, token in enumerate(ordering)}

    def sort_key(pair: Tuple[str, str]) -> Tuple[int, str]:
        token = pair[0]
        return (ordering_index.get(token, len(ordering_index)), token)

    ordered_in = []
    seen = set()
    for token, value in sorted(normalized_in, key=sort_key):
        if (token, value) in seen:
            continue
        seen.add((token, value))
        ordered_in.append((token, value))

    # Optional validation of hierarchy completeness
    if validate_completeness:
        provided_parents = [token for token, _ in ordered_in]
        is_valid, missing, error_msg = validate_geography_hierarchy(
            dataset, year, for_token, provided_parents
        )
        if not is_valid:
            raise ValueError(error_msg)

    return for_token, for_value, ordered_in


def validate_geography_hierarchy(
    dataset: str,
    year: int,
    for_token: str,
    provided_parents: List[str],
) -> Tuple[bool, List[str], str]:
    """
    Validate that all required parent geographies are provided.

    Args:
        dataset: Census dataset (e.g., "acs/acs5")
        year: Census year
        for_token: Target geography token (e.g., "county")
        provided_parents: List of parent geography tokens that were provided

    Returns:
        Tuple of (is_valid, missing_parents, error_message)

    Example:
        >>> validate_geography_hierarchy("acs/acs5", 2023, "county", ["state"])
        (True, [], "")
        >>> validate_geography_hierarchy("acs/acs5", 2023, "county", [])
        (False, ["state"], "Missing required parent geography: state. For 'county', you must specify: ['state']")
    """
    # Get expected hierarchy ordering
    ordering = get_hierarchy_ordering(dataset, year, for_token)

    if not ordering:
        # No hierarchy information available - assume valid
        logger.debug(
            f"No hierarchy ordering found for {dataset}/{year}/{for_token}, skipping validation"
        )
        return (True, [], "")

    # Check if all required parents are provided
    provided_set = set(provided_parents)
    required_set = set(ordering)
    missing = required_set - provided_set

    if missing:
        missing_list = sorted(
            missing, key=lambda x: ordering.index(x) if x in ordering else 999
        )
        error_msg = (
            f"Missing required parent geography: {', '.join(missing_list)}. "
            f"For '{for_token}', you must specify: {ordering}"
        )

        # Try to get example URL from metadata
        client = initialize_chroma_client()
        if not isinstance(client, dict):
            try:
                collection = client.get_collection(
                    CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME
                )
                result = collection.get(
                    where={
                        "$and": [
                            {"dataset": {"$eq": dataset}},
                            {"year": {"$eq": year}},
                            {"for_level": {"$eq": for_token}},
                        ]
                    },
                    include=["metadatas"],
                )
                metadatas = result.get("metadatas") or []
                if metadatas and metadatas[0].get("example_url"):
                    error_msg += f"\n\nExample: {metadatas[0]['example_url']}"
            except Exception as e:
                logger.debug(f"Could not fetch example URL: {e}")

        logger.warning(error_msg)
        return (False, missing_list, error_msg)

    return (True, [], "")
