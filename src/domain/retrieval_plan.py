"""Versioned evidence and selection contracts for grounded Census planning."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.geography_catalog import CatalogCandidate

RETRIEVAL_PLAN_CONTRACT_VERSION = "1.0"
EvidenceStatus = Literal["hit", "empty", "unavailable", "stale", "schema_mismatch"]
SelectionStatus = Literal["selected", "ambiguous", "rejected"]


class RetrievalPlanContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = RETRIEVAL_PLAN_CONTRACT_VERSION


class RetrievalEvidence(RetrievalPlanContract):
    evidence_id: str = Field(min_length=1)
    collection_name: str = Field(min_length=1)
    status: EvidenceStatus
    query_text: str = Field(min_length=1)
    index_version: str | None = None
    schema_version: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    candidates: list[CatalogCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def candidate_ids_match_candidates(self) -> RetrievalEvidence:
        embedded_ids = [candidate.candidate_id for candidate in self.candidates]
        if embedded_ids and self.candidate_ids != embedded_ids:
            raise ValueError("candidate_ids must match candidates in order")
        if self.status == "hit" and not self.candidate_ids:
            raise ValueError("hit evidence must contain candidate_ids")
        if self.status != "hit" and self.candidate_ids:
            raise ValueError("non-hit evidence cannot contain candidate_ids")
        return self


class GroundedSelection(RetrievalPlanContract):
    selection_id: str = Field(min_length=1)
    status: SelectionStatus
    evidence_ids: list[str] = Field(min_length=1)
    selected_hierarchy_id: str | None = None
    selected_area_ids: list[str] = Field(default_factory=list)
    selected_table_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None

    @model_validator(mode="after")
    def selected_status_has_a_candidate(self) -> GroundedSelection:
        selected = bool(self.selected_hierarchy_id or self.selected_area_ids or self.selected_table_ids)
        if self.status == "selected" and not selected:
            raise ValueError("selected status requires at least one selected candidate")
        if self.status != "selected" and selected:
            raise ValueError("ambiguous or rejected selections cannot contain selected candidates")
        return self


class ValidationFailure(RetrievalPlanContract):
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    field_path: str | None = None
    candidate_id: str | None = None
    evidence_id: str | None = None
    retryable: bool = False


__all__ = [
    "EvidenceStatus",
    "GroundedSelection",
    "RETRIEVAL_PLAN_CONTRACT_VERSION",
    "RetrievalEvidence",
    "SelectionStatus",
    "ValidationFailure",
]
