"""
Variable validation utilities leveraging the census_vars Chroma collection
with live variables.json fallback.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from src.utils.chroma_utils import (
    get_chroma_collection_variables,
    initialize_chroma_client,
)
from src.utils.telemetry import record_event

logger = logging.getLogger(__name__)


class VariableValidationError(RuntimeError):
    """Raised when validation cannot be performed."""


def _split_years(years_value: Optional[str]) -> List[str]:
    if not years_value:
        return []
    if isinstance(years_value, (list, tuple)):
        return [str(item).strip() for item in years_value if str(item).strip()]
    return [part.strip() for part in str(years_value).split(",") if part.strip()]


def _table_prefix(variable: str) -> str:
    if "_" in variable:
        return variable.split("_", 1)[0]
    return variable


@lru_cache(maxsize=32)
def _fetch_variables_json(dataset: str, year: int) -> Dict[str, Dict]:
    """
    Fetch the live variables.json catalog for the given dataset/year.
    Results are cached via lru_cache.
    """
    url = f"https://api.census.gov/data/{year}/{dataset}/variables.json"
    logger.info("Fetching live variables metadata: %s", url)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        logger.error("Failed to fetch variables.json: %s", exc)
        raise VariableValidationError(f"Failed to fetch variables.json: {exc}") from exc

    payload = response.json()
    catalog = payload.get("variables")
    if not isinstance(catalog, dict):
        raise VariableValidationError("variables.json response missing 'variables'")
    return catalog


def _score_candidate(
    target_prefix: str,
    target_concept: str,
    target_label: str,
    candidate_name: str,
    candidate_meta: Dict,
) -> int:
    score = 0
    candidate_prefix = _table_prefix(candidate_name)
    candidate_concept = (candidate_meta.get("concept") or "").strip().lower()
    candidate_label = (candidate_meta.get("label") or "").strip().lower()

    if candidate_prefix == target_prefix:
        score += 3
    if target_concept and candidate_concept == target_concept:
        score += 4
    elif target_concept and target_concept in candidate_concept:
        score += 2
    if target_label and target_label in candidate_label:
        score += 1
    return score


def _suggest_alternatives(
    variable: str,
    target_meta: Optional[Dict],
    catalog: Dict[str, Dict],
    max_results: int = 5,
) -> List[str]:
    target_prefix = _table_prefix(variable)
    target_concept = (target_meta or {}).get("concept", "")
    target_label = (target_meta or {}).get("label", "")
    target_concept_lower = target_concept.strip().lower()
    target_label_lower = target_label.strip().lower()

    scored: List[Tuple[int, str]] = []
    for candidate_name, candidate_meta in catalog.items():
        if candidate_name == variable:
            continue
        score = _score_candidate(
            target_prefix,
            target_concept_lower,
            target_label_lower,
            candidate_name,
            candidate_meta,
        )
        if score > 0:
            scored.append((score, candidate_name))

    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored:
        return [name for _, name in scored[:max_results]]

    prefix_stub = target_prefix[:3]
    fallback = [
        name
        for name in sorted(catalog.keys())
        if name != variable and name.startswith(prefix_stub)
    ]
    if fallback:
        return fallback[:max_results]

    remaining = [name for name in sorted(catalog.keys()) if name != variable]
    return remaining[:max_results]


def _normalize_variable_payload(metadata: Dict) -> Dict[str, str]:
    return {
        "concept": metadata.get("concept"),
        "label": metadata.get("label"),
        "universe": metadata.get("universe"),
        "dataset": metadata.get("dataset"),
    }


def validate_variables(
    dataset: str, year: int, variables: Iterable[str]
) -> Dict[str, object]:
    """
    Validate Census API variables against stored metadata with live fallback.
    Returns:
        {
          "valid": [...],
          "invalid": [...],
          "years_available": {var: [years]},
          "details": {var: {...}},
          "alternatives": {var: [...]},
          "source": {var: "chroma" | "live"},
          "warnings": [..]
        }
    """
    dataset = dataset.strip()
    year_str = str(year)
    variables = [var.strip() for var in variables if var and var.strip()]

    result = {
        "valid": [],
        "invalid": [],
        "years_available": {},
        "details": {},
        "alternatives": {},
        "source": {},
        "warnings": [],
    }

    if not variables:
        result["warnings"].append("No variables provided for validation.")
        return result

    client = initialize_chroma_client()
    collection = None
    if isinstance(client, dict):
        result["warnings"].append(client.get("error", "Failed to connect to Chroma."))
    else:
        collection_candidate = get_chroma_collection_variables(client)
        if isinstance(collection_candidate, dict):
            result["warnings"].append(
                collection_candidate.get(
                    "error", "Chroma variables collection unavailable."
                )
            )
        else:
            collection = collection_candidate

    metadata_map: Dict[str, Dict] = {}
    if collection is not None:
        try:
            response = collection.get(
                where={
                    "$and": [
                        {"dataset": {"$eq": dataset}},
                        {"var": {"$in": variables}},
                    ]
                },
                include=["metadatas"],
            )
            for meta in response.get("metadatas") or []:
                var_name = meta.get("var")
                if var_name:
                    metadata_map[var_name] = meta
        except Exception as exc:
            warning = f"Chroma lookup failed: {exc}"
            logger.error(warning)
            result["warnings"].append(warning)

    pending_live_lookup: List[str] = []

    for var in variables:
        metadata = metadata_map.get(var)
        if metadata:
            years = _split_years(metadata.get("years_available"))
            result["years_available"][var] = years
            result["details"][var] = _normalize_variable_payload(metadata)

            if year_str in years or not years:
                result["valid"].append(var)
                result["source"][var] = "chroma"
                continue

        # Collect for live lookup
        pending_live_lookup.append(var)

    live_catalog: Dict[str, Dict] = {}
    if pending_live_lookup:
        try:
            live_catalog = _fetch_variables_json(dataset, year)
        except VariableValidationError as exc:
            result["warnings"].append(str(exc))
        except Exception as exc:
            warning = f"Unexpected error fetching live variables: {exc}"
            logger.error(warning)
            result["warnings"].append(warning)
        else:
            # Augment metadata_map with live payload for reuse
            for var_name, meta in live_catalog.items():
                if var_name not in metadata_map and meta:
                    enriched = dict(meta)
                    enriched["dataset"] = dataset
                    metadata_map[var_name] = enriched

    for var in pending_live_lookup:
        if var in live_catalog:
            metadata = metadata_map.get(var, live_catalog[var])
            result["valid"].append(var)
            result["source"][var] = "live"
            result["years_available"][var] = sorted(
                set(result["years_available"].get(var, []) + [year_str])
            )
            result["details"][var] = _normalize_variable_payload(metadata)
        else:
            result["invalid"].append(var)
            metadata = metadata_map.get(var)
            catalog = live_catalog or metadata_map
            result["alternatives"][var] = _suggest_alternatives(var, metadata, catalog)
            if metadata:
                result["details"][var] = _normalize_variable_payload(metadata)

    record_event(
        "variable_validation",
        {
            "dataset": dataset,
            "year": year,
            "requested": variables,
            "valid": result["valid"],
            "invalid": result["invalid"],
            "warnings": result["warnings"],
        },
    )

    return result


def list_variables(
    dataset: str,
    year: int,
    table_code: Optional[str] = None,
    concept: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, object]:
    """
    Return a filtered list of variables for dataset/year.
    """
    dataset = dataset.strip()
    catalog = _fetch_variables_json(dataset, year)

    table_prefix = table_code.strip() if table_code else None
    concept_lower = concept.lower() if concept else None

    matches: List[Tuple[str, Dict]] = []
    for name, meta in catalog.items():
        if table_prefix and _table_prefix(name) != table_prefix:
            continue
        if concept_lower and concept_lower not in (meta.get("concept") or "").lower():
            continue
        matches.append((name, meta))

    matches.sort(key=lambda item: item[0])
    trimmed = matches[:limit] if limit else matches

    response = {
        "dataset": dataset,
        "year": year,
        "count": len(trimmed),
        "variables": [
            {
                "var": name,
                "label": meta.get("label"),
                "concept": meta.get("concept"),
                "universe": meta.get("universe"),
            }
            for name, meta in trimmed
        ],
    }

    record_event(
        "variable_list",
        {
            "dataset": dataset,
            "year": year,
            "table_code": table_prefix,
            "concept": concept_lower,
            "limit": limit,
            "returned": response["count"],
        },
    )

    return response


__all__ = ["validate_variables", "list_variables", "VariableValidationError"]
