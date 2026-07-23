"""Fake Chroma evidence for Phase 6 clarification policy tests."""

from __future__ import annotations

from dataclasses import dataclass

from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.domain.geography_catalog import AreaCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.chroma_catalog_retriever import GeographyRetrievalResult


@dataclass(frozen=True)
class AreaSpec:
    candidate_id: str
    label: str
    token: str
    code: str
    score: float


class ClarificationChromaFake(FakeGroundedRetrieval):
    """Return controlled official-shaped area hits while preserving table evidence."""

    def __init__(self, areas: list[AreaSpec], *, status: str = "hit"):
        super().__init__()
        self.areas = areas
        self.status = status

    def retrieve_geographies(self, analysis, *, dataset: str, year: int) -> GeographyRetrievalResult:
        base = super().retrieve_geographies(analysis, dataset=dataset, year=year)
        candidates = [
            AreaCandidate(
                candidate_id=spec.candidate_id,
                dataset=dataset,
                year=year,
                display_name=spec.label,
                score=spec.score,
                provenance="census_api",
                schema_version="1.0",
                friendly_level=spec.token,
                census_token=spec.token,
                geo_id=f"phase6-{spec.candidate_id}",
                geography_code=spec.code,
            )
            for spec in self.areas
        ]
        area_evidence = RetrievalEvidence(
            evidence_id="phase6-area-evidence",
            collection_name="census_geography_areas",
            status=self.status,
            query_text=analysis.area_search_texts[0] if analysis.area_search_texts else analysis.question,
            index_version="phase6-fake-v1",
            schema_version="1.0",
            candidate_ids=[candidate.candidate_id for candidate in candidates] if self.status == "hit" else [],
            candidates=candidates if self.status == "hit" else [],
        )
        return GeographyRetrievalResult(
            hierarchy_evidence=base.hierarchy_evidence,
            area_evidence=[area_evidence],
        )


AMBIGUOUS_AREAS = {
    "Springfield": [
        AreaSpec("area:springfield-il", "Springfield, Illinois", "state", "17", 0.98),
        AreaSpec("area:springfield-ma", "Springfield, Massachusetts", "state", "25", 0.97),
    ],
    "Portland": [
        AreaSpec("area:portland-me", "Portland, Maine", "state", "23", 0.98),
        AreaSpec("area:portland-or", "Portland, Oregon", "state", "41", 0.97),
    ],
    "New York": [
        AreaSpec("area:new-york-state", "New York State", "state", "36", 0.98),
        AreaSpec("area:new-york-city", "New York city, New York", "place", "51000", 0.97),
    ],
}


__all__ = ["AMBIGUOUS_AREAS", "AreaSpec", "ClarificationChromaFake"]
