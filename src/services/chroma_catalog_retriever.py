"""Grounded catalog retrieval with mandatory table and constrained geography queries."""

from __future__ import annotations

import hashlib
from typing import Any

from chromadb.api import ClientAPI
from pydantic import BaseModel, ConfigDict, Field

from config import CHROMA_RETRIEVAL_TOP_K
from src.clients.chroma_utils import (
    ChromaCatalogQueryResult,
    initialize_chroma_client,
    query_area_collection,
    query_dataset_geography_collection,
    query_table_collection,
)
from src.domain.geography_catalog import TableCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis


class GeographyRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hierarchy_evidence: RetrievalEvidence
    area_evidence: list[RetrievalEvidence] = Field(default_factory=list)

    @property
    def evidence(self) -> list[RetrievalEvidence]:
        return [self.hierarchy_evidence, *self.area_evidence]


def _evidence_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha256(payload.encode()).hexdigest()[:20]}"


def _unavailable(collection_name: str, query_text: str, evidence_id: str, reason: str) -> RetrievalEvidence:
    return RetrievalEvidence(
        evidence_id=evidence_id,
        collection_name=collection_name,
        status="unavailable",
        query_text=query_text,
    )


def _to_evidence(result: ChromaCatalogQueryResult, evidence_id: str) -> RetrievalEvidence:
    return RetrievalEvidence(
        evidence_id=evidence_id,
        collection_name=result.collection_name,
        status=result.status,
        query_text=result.query_text,
        index_version=result.index_version,
        schema_version=result.schema_version,
        candidate_ids=result.candidate_ids,
        candidates=result.candidates,
    )


def _client_or_error(client: ClientAPI | None) -> tuple[ClientAPI | None, str | None]:
    if client is not None:
        return client, None
    initialized = initialize_chroma_client()
    if isinstance(initialized, dict):
        return None, str(initialized.get("error", "Chroma is unavailable"))
    return initialized, None


def retrieve_table_candidates(
    analysis: CensusRetrievalAnalysis | str,
    *,
    client: ClientAPI | None = None,
    dataset: str | None = None,
    year: int | None = None,
    top_k: int = CHROMA_RETRIEVAL_TOP_K,
) -> RetrievalEvidence:
    """Always execute the table catalog query; no ungrounded fallback is permitted."""
    query_text = analysis.table_search_text if isinstance(analysis, CensusRetrievalAnalysis) else analysis
    query_text = query_text.strip()
    if not query_text:
        raise ValueError("table search text is required")
    evidence_id = _evidence_id("table-evidence", query_text, dataset, year)
    resolved_client, error = _client_or_error(client)
    if resolved_client is None:
        return _unavailable("census_tables", query_text, evidence_id, error or "Chroma is unavailable")

    where: dict[str, Any] | None = {"dataset": {"$eq": dataset}} if dataset else None
    result = query_table_collection(resolved_client, query_text, where=where, n_results=top_k)
    if result.status == "hit" and year is not None:
        filtered = [
            candidate
            for candidate in result.candidates
            if isinstance(candidate, TableCandidate) and year in candidate.years_available
        ]
        result = result.model_copy(
            update={
                "status": "hit" if filtered else "empty",
                "candidate_ids": [candidate.candidate_id for candidate in filtered],
                "candidates": filtered,
                "reason": None if filtered else f"no table candidates are available in {year}",
            }
        )
    return _to_evidence(result, evidence_id)


def retrieve_geography_candidates(
    analysis: CensusRetrievalAnalysis,
    *,
    dataset: str,
    year: int,
    client: ClientAPI | None = None,
    top_k: int = CHROMA_RETRIEVAL_TOP_K,
) -> GeographyRetrievalResult:
    """Retrieve hierarchy and area evidence only inside a dataset/year partition."""
    if not dataset.strip():
        raise ValueError("dataset is required for geography retrieval")
    resolved_client, error = _client_or_error(client)
    hierarchy_id = _evidence_id("hierarchy-evidence", analysis.geography_search_text, dataset, year)
    if resolved_client is None:
        hierarchy = _unavailable(
            "census_dataset_geographies",
            analysis.geography_search_text,
            hierarchy_id,
            error or "Chroma is unavailable",
        )
        areas = [
            _unavailable(
                "census_geography_areas",
                query,
                _evidence_id("area-evidence", query, dataset, year),
                error or "Chroma is unavailable",
            )
            for query in analysis.area_search_texts
        ]
        return GeographyRetrievalResult(hierarchy_evidence=hierarchy, area_evidence=areas)

    hierarchy_result = query_dataset_geography_collection(
        resolved_client,
        analysis.geography_search_text,
        dataset=dataset,
        year=year,
        n_results=top_k,
    )
    hierarchy = _to_evidence(hierarchy_result, hierarchy_id)
    areas = []
    for query in analysis.area_search_texts:
        result = query_area_collection(
            resolved_client,
            query,
            dataset=dataset,
            year=year,
            n_results=top_k,
        )
        areas.append(_to_evidence(result, _evidence_id("area-evidence", query, dataset, year)))
    return GeographyRetrievalResult(hierarchy_evidence=hierarchy, area_evidence=areas)


__all__ = ["GeographyRetrievalResult", "retrieve_geography_candidates", "retrieve_table_candidates"]
