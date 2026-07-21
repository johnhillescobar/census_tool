"""
Chroma database utilities for Census variable retrieval
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from config import (
    CHROMA_CATALOG_INDEX_VERSION,
    CHROMA_CATALOG_SCHEMA_VERSION,
    CHROMA_COLLECTION_NAME,
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
    CHROMA_INDEX_MAX_AGE_SECONDS,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
)
from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate, TableCandidate
from src.domain.retrieval_plan import EvidenceStatus

logger = logging.getLogger(__name__)

CatalogCollectionKind = Literal["table", "hierarchy", "area"]


class ChromaCatalogQueryResult(BaseModel):
    """Validated result from one catalog collection query."""

    model_config = ConfigDict(extra="forbid")

    status: EvidenceStatus
    collection_name: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    collection_kind: CatalogCollectionKind
    index_version: str | None = None
    schema_version: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    candidates: list[TableCandidate | HierarchyCandidate | AreaCandidate] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def status_matches_candidates(self) -> ChromaCatalogQueryResult:
        if self.status == "hit" and (not self.candidate_ids or len(self.candidate_ids) != len(self.candidates)):
            raise ValueError("hit result requires matching candidate IDs and candidates")
        if self.status != "hit" and (self.candidate_ids or self.candidates):
            raise ValueError("non-hit result cannot contain candidates")
        return self


class TableCollectionQueryResult(ChromaCatalogQueryResult):
    collection_kind: Literal["table"] = "table"
    candidates: list[TableCandidate] = Field(default_factory=list)


class DatasetGeographyCollectionQueryResult(ChromaCatalogQueryResult):
    collection_kind: Literal["hierarchy"] = "hierarchy"
    candidates: list[HierarchyCandidate] = Field(default_factory=list)


class AreaCollectionQueryResult(ChromaCatalogQueryResult):
    collection_kind: Literal["area"] = "area"
    candidates: list[AreaCandidate] = Field(default_factory=list)


class HierarchyLookupResult(BaseModel):
    """Typed, fail-closed hierarchy lookup for grounded planning."""

    model_config = ConfigDict(extra="forbid")

    status: EvidenceStatus
    dataset: str
    year: int
    for_level: str
    ordering: list[str] = Field(default_factory=list)
    hierarchy_id: str | None = None
    reason: str | None = None


class HierarchyValidationResult(BaseModel):
    """Explicit validation outcome; every non-valid status is fail-closed."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "invalid", "empty", "unavailable", "stale", "schema_mismatch"]
    dataset: str
    year: int
    for_level: str
    required_parents: list[str] = Field(default_factory=list)
    provided_parents: list[str] = Field(default_factory=list)
    missing_parents: list[str] = Field(default_factory=list)
    hierarchy_id: str | None = None
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status == "valid"


_GEO_TOKEN_CANONICAL = {
    "nation": "us",
    "cbsa": "metropolitan statistical area/micropolitan statistical area",
    "msa": "metropolitan statistical area/micropolitan statistical area",
    "metropolitan statistical area": "metropolitan statistical area/micropolitan statistical area",
    "micropolitan statistical area": "metropolitan statistical area/micropolitan statistical area",
}


def initialize_chroma_client() -> ClientAPI | dict[str, str | list[str]]:
    """Initialize and return Chroma client"""
    try:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False))

    except Exception as e:
        logger.error(f"Failed to connect to Chroma: {e}")
        return {
            "error": f"Failed to connect to variable database: {e}",
            "logs": ["retrieve: ERROR - Chroma connection failed"],
        }

    return client


def get_chroma_collection_variables(
    client: ClientAPI,
) -> chromadb.Collection | dict[str, str | list[str]]:
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
    client: ClientAPI,
) -> chromadb.Collection | dict[str, str | list[str]]:
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


def _collection_health(collection: Any) -> tuple[EvidenceStatus | None, str | None, str | None, str | None]:
    metadata = collection.metadata or {}
    schema_version = metadata.get("schema_version")
    index_version = metadata.get("index_version")
    if schema_version != CHROMA_CATALOG_SCHEMA_VERSION:
        return "schema_mismatch", str(schema_version) if schema_version is not None else None, (
            str(index_version) if index_version is not None else None
        ), "collection schema version is missing or unsupported"
    if index_version != CHROMA_CATALOG_INDEX_VERSION:
        return "stale", str(schema_version), str(index_version) if index_version is not None else None, (
            "collection index version is missing or outdated"
        )

    built_at = metadata.get("built_at") or metadata.get("retrieved_at")
    if isinstance(built_at, str):
        try:
            built = datetime.fromisoformat(built_at.replace("Z", "+00:00"))
            if built.tzinfo is None:
                built = built.replace(tzinfo=UTC)
            if (datetime.now(UTC) - built).total_seconds() > CHROMA_INDEX_MAX_AGE_SECONDS:
                return "stale", str(schema_version), str(index_version), "collection is older than the maximum age"
        except ValueError:
            return "schema_mismatch", str(schema_version), str(index_version), "collection timestamp is malformed"
    return None, str(schema_version), str(index_version), None


def _first_query_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key) or []
    if value and isinstance(value[0], list):
        return list(value[0])
    return list(value)


def _json_list(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [f"{key}:{item}" for key, item in value.items()]
    if not isinstance(value, str):
        raise ValueError("expected JSON list metadata")
    parsed = json.loads(value)
    if isinstance(parsed, dict):
        return [f"{key}:{item}" for key, item in parsed.items()]
    if not isinstance(parsed, list):
        raise ValueError("expected JSON list metadata")
    return [str(item) for item in parsed]


def _years(value: object, fallback: object) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if isinstance(value, str):
        return [int(item) for item in value.split(",") if item.strip()]
    return [int(fallback)] if fallback not in (None, "") else []


def _score(distance: object) -> float | None:
    if not isinstance(distance, int | float):
        return None
    return min(1.0, max(0.0, 1.0 - float(distance)))


def _candidate_from_metadata(
    kind: CatalogCollectionKind,
    candidate_id: str,
    metadata: dict[str, Any],
    distance: object,
) -> TableCandidate | HierarchyCandidate | AreaCandidate:
    if metadata.get("candidate_id") != candidate_id:
        raise ValueError("Chroma id and metadata candidate_id do not match")
    common = {
        "candidate_id": candidate_id,
        "dataset": metadata["dataset"],
        "year": int(metadata["year"]),
        "display_name": metadata.get("display_name")
        or metadata.get("table_name")
        or metadata.get("geography_hierarchy"),
        "score": _score(distance),
        "provenance": metadata["provenance"],
        "schema_version": metadata["schema_version"],
    }
    if kind == "table":
        return TableCandidate(
            **common,
            table_code=metadata["table_code"],
            table_name=metadata["table_name"],
            category=metadata["category"],
            years_available=_years(metadata.get("years_available"), metadata.get("year")),
        )
    if kind == "hierarchy":
        return HierarchyCandidate(
            **common,
            friendly_level=metadata["friendly_level"],
            census_token=metadata["census_token"],
            hierarchy=metadata.get("geography_hierarchy") or metadata["hierarchy"],
            parent_census_tokens=_json_list(metadata.get("parent_census_tokens") or metadata.get("ordering_list")),
            summary_level=str(metadata["summary_level"]) if metadata.get("summary_level") is not None else None,
            aliases=_json_list(metadata.get("aliases")),
            example_urls=_json_list(metadata.get("example_urls")),
        )
    parent_clauses = metadata.get("parent_geo_ids") or metadata.get("parent_clauses")
    return AreaCandidate(
        **common,
        friendly_level=metadata["friendly_level"],
        census_token=metadata["census_token"],
        geo_id=metadata["geo_id"],
        geography_code=str(metadata["geography_code"]),
        parent_geo_ids=_json_list(parent_clauses),
        aliases=_json_list(metadata.get("aliases")),
    )


def query_catalog_collection(
    client: ClientAPI,
    *,
    collection_name: str,
    collection_kind: CatalogCollectionKind,
    query_text: str,
    where: dict[str, Any] | None = None,
    n_results: int = 12,
) -> ChromaCatalogQueryResult:
    """Query a catalog and convert every external shape error into an explicit status."""
    if not query_text.strip():
        raise ValueError("query_text is required")
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        return ChromaCatalogQueryResult(
            status="unavailable",
            collection_name=collection_name,
            collection_kind=collection_kind,
            query_text=query_text,
            reason=str(exc),
        )

    health, schema_version, index_version, reason = _collection_health(collection)
    if health is not None:
        return ChromaCatalogQueryResult(
            status=health,
            collection_name=collection_name,
            collection_kind=collection_kind,
            query_text=query_text,
            schema_version=schema_version,
            index_version=index_version,
            reason=reason,
        )

    try:
        payload = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["metadatas", "documents", "distances"],
        )
        ids = [str(item) for item in _first_query_list(payload, "ids")]
        metadatas = _first_query_list(payload, "metadatas")
        distances = _first_query_list(payload, "distances")
        if not ids:
            return ChromaCatalogQueryResult(
                status="empty",
                collection_name=collection_name,
                collection_kind=collection_kind,
                query_text=query_text,
                schema_version=schema_version,
                index_version=index_version,
            )
        if len(metadatas) != len(ids):
            raise ValueError("query ids and metadatas have different lengths")
        candidates = [
            _candidate_from_metadata(
                collection_kind,
                candidate_id,
                metadata,
                distances[index] if index < len(distances) else None,
            )
            for index, (candidate_id, metadata) in enumerate(zip(ids, metadatas, strict=True))
        ]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        return ChromaCatalogQueryResult(
            status="schema_mismatch",
            collection_name=collection_name,
            collection_kind=collection_kind,
            query_text=query_text,
            schema_version=schema_version,
            index_version=index_version,
            reason=str(exc),
        )
    except Exception as exc:
        return ChromaCatalogQueryResult(
            status="unavailable",
            collection_name=collection_name,
            collection_kind=collection_kind,
            query_text=query_text,
            schema_version=schema_version,
            index_version=index_version,
            reason=str(exc),
        )
    return ChromaCatalogQueryResult(
        status="hit",
        collection_name=collection_name,
        collection_kind=collection_kind,
        query_text=query_text,
        schema_version=schema_version,
        index_version=index_version,
        candidate_ids=ids,
        candidates=candidates,
    )


def query_table_collection(
    client: ClientAPI, query_text: str, *, where: dict[str, Any] | None = None, n_results: int = 12
) -> TableCollectionQueryResult:
    result = query_catalog_collection(
        client,
        collection_name=CHROMA_TABLE_COLLECTION_NAME,
        collection_kind="table",
        query_text=query_text,
        where=where,
        n_results=n_results,
    )
    return TableCollectionQueryResult.model_validate(result.model_dump())


def query_dataset_geography_collection(
    client: ClientAPI, query_text: str, *, dataset: str, year: int, n_results: int = 12
) -> DatasetGeographyCollectionQueryResult:
    result = query_catalog_collection(
        client,
        collection_name=CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
        collection_kind="hierarchy",
        query_text=query_text,
        where={"$and": [{"dataset": {"$eq": dataset}}, {"year": {"$eq": year}}]},
        n_results=n_results,
    )
    return DatasetGeographyCollectionQueryResult.model_validate(result.model_dump())


def query_area_collection(
    client: ClientAPI,
    query_text: str,
    *,
    dataset: str,
    year: int,
    census_token: str | None = None,
    n_results: int = 12,
) -> AreaCollectionQueryResult:
    clauses: list[dict[str, Any]] = [{"dataset": {"$eq": dataset}}, {"year": {"$eq": year}}]
    if census_token:
        clauses.append({"census_token": {"$eq": census_token}})
    result = query_catalog_collection(
        client,
        collection_name=CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
        collection_kind="area",
        query_text=query_text,
        where={"$and": clauses},
        n_results=n_results,
    )
    return AreaCollectionQueryResult.model_validate(result.model_dump())


def _normalize_geo_token(token: str) -> str:
    if not token:
        return token
    key = token.strip().lower()
    return _GEO_TOKEN_CANONICAL.get(key, token.strip())


@lru_cache(maxsize=512)
def get_hierarchy_ordering_result(dataset: str, year: int, for_level: str) -> HierarchyLookupResult:
    """Return hierarchy evidence without treating missing catalog data as success."""
    client = initialize_chroma_client()
    if isinstance(client, dict):
        return HierarchyLookupResult(
            status="unavailable",
            dataset=dataset,
            year=year,
            for_level=for_level,
            reason=str(client.get("error", "Chroma is unavailable")),
        )
    result = query_catalog_collection(
        client,
        collection_name=CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
        collection_kind="hierarchy",
        query_text=for_level,
        where={
            "$and": [
                {"dataset": {"$eq": dataset}},
                {"year": {"$eq": year}},
                {"for_level": {"$eq": for_level}},
            ]
        },
        n_results=1,
    )
    if result.status != "hit":
        return HierarchyLookupResult(
            status=result.status,
            dataset=dataset,
            year=year,
            for_level=for_level,
            reason=result.reason,
        )
    candidate = result.candidates[0]
    if not isinstance(candidate, HierarchyCandidate):
        return HierarchyLookupResult(
            status="schema_mismatch",
            dataset=dataset,
            year=year,
            for_level=for_level,
            reason="hierarchy collection returned a non-hierarchy candidate",
        )
    return HierarchyLookupResult(
        status="hit",
        dataset=dataset,
        year=year,
        for_level=for_level,
        ordering=[_normalize_geo_token(token) for token in candidate.parent_census_tokens],
        hierarchy_id=candidate.candidate_id,
    )


@lru_cache(maxsize=512)
def get_hierarchy_ordering(dataset: str, year: int, for_level: str) -> list[str]:
    """
    Return the expected parent ordering for `for_level` given dataset/year.
    Looks up the census_geography_hierarchies Chroma collection.
    Falls back to [] when no ordering is found.
    """
    # Legacy callers historically used collection.get() and interpreted [] as
    # "no constraint". Keep that behavior until they are migrated.
    client = initialize_chroma_client()
    if isinstance(client, dict):
        return []
    try:
        collection = client.get_collection(CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME)
        payload = collection.get(
            where={
                "$and": [
                    {"dataset": {"$eq": dataset}},
                    {"year": {"$eq": year}},
                    {"for_level": {"$eq": for_level}},
                ]
            },
            include=["metadatas"],
        )
        metadatas = payload.get("metadatas") or []
        ordering_json = metadatas[0].get("ordering_list") if metadatas else None
        if not isinstance(ordering_json, str | bytes | bytearray):
            return []
        ordering = json.loads(ordering_json)
        if not isinstance(ordering, list):
            return []
        return [_normalize_geo_token(str(token)) for token in ordering]
    except Exception as exc:
        logger.error("Hierarchy lookup failed: %s", exc)
        return []


def validate_geography_hierarchy_typed(
    dataset: str,
    year: int,
    for_token: str,
    provided_parents: list[str],
) -> HierarchyValidationResult:
    """Fail closed for complex callers while preserving the legacy tuple API."""
    result = get_hierarchy_ordering_result(dataset, year, for_token)
    normalized_provided = [_normalize_geo_token(token) for token in provided_parents]
    if result.status != "hit":
        return HierarchyValidationResult(
            status=result.status,
            dataset=dataset,
            year=year,
            for_level=for_token,
            provided_parents=normalized_provided,
            hierarchy_id=result.hierarchy_id,
            reason=result.reason or "hierarchy evidence is not usable",
        )
    provided = set(normalized_provided)
    missing = [token for token in result.ordering if token not in provided]
    if missing:
        return HierarchyValidationResult(
            status="invalid",
            dataset=dataset,
            year=year,
            for_level=for_token,
            required_parents=result.ordering,
            provided_parents=normalized_provided,
            missing_parents=missing,
            hierarchy_id=result.hierarchy_id,
            reason=f"missing required parent geography: {', '.join(missing)}",
        )
    return HierarchyValidationResult(
        status="valid",
        dataset=dataset,
        year=year,
        for_level=for_token,
        required_parents=result.ordering,
        provided_parents=normalized_provided,
        hierarchy_id=result.hierarchy_id,
    )


def validate_and_fix_geo_params(
    dataset: str,
    year: int,
    geo_for: dict[str, str],
    geo_in: dict[str, str] | None = None,
    *,
    extra_in: Iterable[tuple[str, str]] | None = None,
    validate_completeness: bool = False,
) -> tuple[str, str, list[tuple[str, str]]]:
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

    normalized_for_items = [(_normalize_geo_token(k), str(v).strip()) for k, v in geo_for.items()]
    # target level is the most granular entry (last given)
    for_token, for_value = normalized_for_items[-1]
    parent_pairs = normalized_for_items[:-1]

    normalized_in = []
    if geo_in:
        normalized_in.extend((_normalize_geo_token(k), str(v).strip()) for k, v in geo_in.items())
    if extra_in:
        normalized_in.extend((_normalize_geo_token(k), str(v).strip()) for k, v in extra_in)
    # Add parents we removed from geo_for
    normalized_in.extend(parent_pairs)

    # Determine ordering
    ordering = get_hierarchy_ordering(dataset, year, for_token) or [token for token, _ in normalized_in]
    ordering_index = {token: idx for idx, token in enumerate(ordering)}

    def sort_key(pair: tuple[str, str]) -> tuple[int, str]:
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
        is_valid, missing, error_msg = validate_geography_hierarchy(dataset, year, for_token, provided_parents)
        if not is_valid:
            raise ValueError(error_msg)

    return for_token, for_value, ordered_in


def validate_geography_hierarchy(
    dataset: str,
    year: int,
    for_token: str,
    provided_parents: list[str],
) -> tuple[bool, list[str], str]:
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
        logger.debug(f"No hierarchy ordering found for {dataset}/{year}/{for_token}, skipping validation")
        return (True, [], "")

    # Check if all required parents are provided
    provided_set = set(provided_parents)
    required_set = set(ordering)
    missing = required_set - provided_set

    if missing:
        missing_list = sorted(missing, key=lambda x: ordering.index(x) if x in ordering else 999)
        error_msg = (
            f"Missing required parent geography: {', '.join(missing_list)}. For '{for_token}', you must specify: {ordering}"
        )

        # Try to get example URL from metadata
        client = initialize_chroma_client()
        if not isinstance(client, dict):
            try:
                collection = client.get_collection(CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME)
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
