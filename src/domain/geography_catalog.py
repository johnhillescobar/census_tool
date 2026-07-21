"""Versioned contracts shared by Census catalog index builders and retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CATALOG_CONTRACT_VERSION = "1.0"
ChromaScalar = str | int | float | bool
CandidateKind = Literal["hierarchy", "area", "table"]
ProvenanceKind = Literal["census_geography", "census_examples", "census_api", "census_groups"]


class CatalogContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = CATALOG_CONTRACT_VERSION


class DatasetGeographyLevel(CatalogContract):
    """An authoritative geography level advertised by a Census dataset."""

    candidate_id: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    year: int = Field(ge=2000)
    friendly_level: str = Field(min_length=1)
    census_token: str = Field(min_length=1)
    hierarchy: str = Field(min_length=1)
    summary_level: str | None = None
    parent_census_tokens: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    source_url: str = Field(min_length=1)
    provenance: ProvenanceKind = "census_geography"
    schema_version: str = Field(min_length=1)


class CandidateContract(CatalogContract):
    candidate_id: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    year: int = Field(ge=2000)
    display_name: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    provenance: ProvenanceKind
    schema_version: str = Field(min_length=1)


class HierarchyCandidate(CandidateContract):
    candidate_kind: Literal["hierarchy"] = "hierarchy"
    friendly_level: str = Field(min_length=1)
    census_token: str = Field(min_length=1)
    hierarchy: str = Field(min_length=1)
    parent_census_tokens: list[str] = Field(default_factory=list)
    summary_level: str | None = None
    aliases: list[str] = Field(default_factory=list)
    example_urls: list[str] = Field(default_factory=list)


class AreaCandidate(CandidateContract):
    candidate_kind: Literal["area"] = "area"
    friendly_level: str = Field(min_length=1)
    census_token: str = Field(min_length=1)
    geo_id: str = Field(min_length=1)
    geography_code: str = Field(min_length=1)
    parent_geo_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class TableCandidate(CandidateContract):
    candidate_kind: Literal["table"] = "table"
    table_code: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    years_available: list[int] = Field(default_factory=list)


CatalogCandidate = Annotated[
    HierarchyCandidate | AreaCandidate | TableCandidate,
    Field(discriminator="candidate_kind"),
]


class IndexManifest(CatalogContract):
    """Portable build receipt; its JSON is stored beside, not inside, Chroma."""

    collection_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    document_count: int = Field(ge=0)
    datasets: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    partitions: list[str] = Field(default_factory=list)
    metadata: dict[str, ChromaScalar] = Field(default_factory=dict)


# Explicit aliases keep call sites readable while the catalog contract remains compact.
GeographyHierarchyCandidate = HierarchyCandidate
GeographyAreaCandidate = AreaCandidate

__all__ = [
    "AreaCandidate",
    "CATALOG_CONTRACT_VERSION",
    "CatalogCandidate",
    "ChromaScalar",
    "DatasetGeographyLevel",
    "GeographyAreaCandidate",
    "GeographyHierarchyCandidate",
    "HierarchyCandidate",
    "IndexManifest",
    "TableCandidate",
]
