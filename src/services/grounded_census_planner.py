"""Candidate-ID-only selection policy for grounded Census plans."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from config import CHROMA_RETRIEVAL_AMBIGUITY_MARGIN, CHROMA_RETRIEVAL_MIN_SCORE
from src.domain.geography_catalog import TableCandidate
from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence
from src.services.chroma_catalog_retriever import GeographyRetrievalResult

_NON_WORD = re.compile(r"[^\w]+")


class CandidateIdSelection(BaseModel):
    """Safe output shape for a future LLM selector: IDs, never canonical values."""

    model_config = ConfigDict(extra="forbid")

    table_id: str | None = None
    hierarchy_id: str | None = None
    area_ids: list[str] = Field(default_factory=list)


def _selection_id(evidence: Iterable[RetrievalEvidence]) -> str:
    ids = "\x1f".join(item.evidence_id for item in evidence)
    return f"selection:{hashlib.sha256(ids.encode()).hexdigest()[:20]}"


def _normalized_label(value: str) -> str:
    return _NON_WORD.sub(" ", value.casefold()).strip()


def _exact_table_match_id(evidence: RetrievalEvidence, *, minimum_score: float) -> str | None:
    """Prefer a unique exact table_name/code match to the retrieval query over a thin score margin."""
    if evidence.status != "hit":
        return None
    needle = _normalized_label(evidence.query_text)
    if not needle:
        return None
    matches: list[tuple[float, str]] = []
    for candidate in evidence.candidates:
        if not isinstance(candidate, TableCandidate):
            continue
        score = candidate.score if candidate.score is not None else 0.0
        if score < minimum_score:
            continue
        labels = {
            _normalized_label(candidate.table_name),
            _normalized_label(candidate.display_name),
            _normalized_label(candidate.table_code),
        }
        if needle in labels:
            matches.append((score, candidate.candidate_id))
    if len(matches) != 1:
        return None
    return matches[0][1]


def _ranked_id(
    evidence: RetrievalEvidence,
    *,
    minimum_score: float,
    ambiguity_margin: float,
) -> tuple[str | None, str | None]:
    if evidence.status != "hit":
        return None, f"{evidence.collection_name.upper()}_{evidence.status.upper()}"
    exact_table_id = _exact_table_match_id(evidence, minimum_score=minimum_score)
    if exact_table_id is not None:
        return exact_table_id, None
    ranked = sorted(
        (
            (candidate.score if candidate.score is not None else 0.0, candidate.candidate_id)
            for candidate in evidence.candidates
        ),
        key=lambda item: (-item[0], item[1]),
    )
    if not ranked or ranked[0][0] < minimum_score:
        return None, "CANDIDATE_SCORE_BELOW_THRESHOLD"
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < ambiguity_margin:
        return None, "CANDIDATE_AMBIGUOUS"
    return ranked[0][1], None


def _proposed_ids_are_grounded(
    proposed: CandidateIdSelection,
    table_evidence: RetrievalEvidence,
    geography_evidence: GeographyRetrievalResult | None,
) -> bool:
    selected = [item for item in [proposed.table_id, proposed.hierarchy_id, *proposed.area_ids] if item is not None]
    if len(selected) != len(set(selected)) or proposed.table_id not in table_evidence.candidate_ids:
        return False
    if geography_evidence is None:
        return proposed.hierarchy_id is None and not proposed.area_ids
    if proposed.hierarchy_id not in geography_evidence.hierarchy_evidence.candidate_ids:
        return False
    if len(proposed.area_ids) != len(geography_evidence.area_evidence):
        return False
    return all(
        candidate_id in area_evidence.candidate_ids
        for candidate_id, area_evidence in zip(proposed.area_ids, geography_evidence.area_evidence, strict=True)
    )


def _evidence_bundle(
    table_evidence: RetrievalEvidence,
    geography_evidence: GeographyRetrievalResult | None,
) -> tuple[list[str], str]:
    evidence = [table_evidence]
    if geography_evidence is not None:
        evidence.extend(geography_evidence.evidence)
    evidence_ids = [item.evidence_id for item in evidence]
    return evidence_ids, _selection_id(evidence)


def validate_proposed_grounded_ids(
    proposed: CandidateIdSelection,
    table_evidence: RetrievalEvidence,
    geography_evidence: GeographyRetrievalResult | None = None,
) -> GroundedSelection:
    """Verify agent-proposed candidate IDs are grounded in retrieval evidence."""
    evidence_ids, selection_id = _evidence_bundle(table_evidence, geography_evidence)

    if not proposed.table_id:
        return GroundedSelection(
            selection_id=selection_id,
            status="rejected",
            evidence_ids=evidence_ids,
            reason_code="TABLE_SELECTION_REQUIRED",
        )
    if not _proposed_ids_are_grounded(proposed, table_evidence, geography_evidence):
        return GroundedSelection(
            selection_id=selection_id,
            status="rejected",
            evidence_ids=evidence_ids,
            reason_code="UNKNOWN_CANDIDATE_ID",
        )
    return GroundedSelection(
        selection_id=selection_id,
        status="selected",
        evidence_ids=evidence_ids,
        selected_table_ids=[proposed.table_id],
        selected_hierarchy_id=proposed.hierarchy_id,
        selected_area_ids=proposed.area_ids,
    )


def select_grounded_plan(
    table_evidence: RetrievalEvidence,
    geography_evidence: GeographyRetrievalResult | None = None,
    *,
    proposed: CandidateIdSelection | None = None,
    minimum_score: float = CHROMA_RETRIEVAL_MIN_SCORE,
    ambiguity_margin: float = CHROMA_RETRIEVAL_AMBIGUITY_MARGIN,
) -> GroundedSelection:
    """Select only opaque IDs supplied by retrieval evidence."""
    if proposed is not None:
        return validate_proposed_grounded_ids(proposed, table_evidence, geography_evidence)

    evidence_ids, selection_id = _evidence_bundle(table_evidence, geography_evidence)

    table_id, reason = _ranked_id(
        table_evidence,
        minimum_score=minimum_score,
        ambiguity_margin=ambiguity_margin,
    )
    if table_id is None:
        status = "ambiguous" if reason == "CANDIDATE_AMBIGUOUS" else "rejected"
        return GroundedSelection(
            selection_id=selection_id,
            status=status,
            evidence_ids=evidence_ids,
            reason_code=reason,
        )

    hierarchy_id: str | None = None
    area_ids: list[str] = []
    if geography_evidence is not None:
        hierarchy_id, reason = _ranked_id(
            geography_evidence.hierarchy_evidence,
            minimum_score=minimum_score,
            ambiguity_margin=ambiguity_margin,
        )
        if hierarchy_id is None:
            status = "ambiguous" if reason == "CANDIDATE_AMBIGUOUS" else "rejected"
            return GroundedSelection(
                selection_id=selection_id,
                status=status,
                evidence_ids=evidence_ids,
                reason_code=reason,
            )
        for area_evidence in geography_evidence.area_evidence:
            area_id, reason = _ranked_id(
                area_evidence,
                minimum_score=minimum_score,
                ambiguity_margin=ambiguity_margin,
            )
            if area_id is None:
                status = "ambiguous" if reason == "CANDIDATE_AMBIGUOUS" else "rejected"
                return GroundedSelection(
                    selection_id=selection_id,
                    status=status,
                    evidence_ids=evidence_ids,
                    reason_code=reason,
                )
            area_ids.append(area_id)

    return GroundedSelection(
        selection_id=selection_id,
        status="selected",
        evidence_ids=evidence_ids,
        selected_table_ids=[table_id],
        selected_hierarchy_id=hierarchy_id,
        selected_area_ids=area_ids,
    )


__all__ = ["CandidateIdSelection", "select_grounded_plan", "validate_proposed_grounded_ids"]
