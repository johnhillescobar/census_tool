"""Phase 6 single-turn clarification policy over fake Chroma evidence."""

from __future__ import annotations

import pytest

from app_test_scripts.phase6_clarification_fakes import (
    AMBIGUOUS_AREAS,
    AreaSpec,
    ClarificationChromaFake,
)
from src.services.graph_session import build_fresh_thread_state
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _run(question: str, fake: ClarificationChromaFake):
    state = build_fresh_thread_state(question)
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    return geography_node(state, {}, dependencies=fake.dependencies())


@pytest.mark.parametrize("place", ["Springfield", "Portland", "New York"])
def test_ambiguous_places_only_offer_labels_from_retrieved_chroma_evidence(place):
    fake = ClarificationChromaFake(AMBIGUOUS_AREAS[place])
    result = _run(f"Show total population for counties in {place} in 2023", fake)
    plan = result["plan"]
    pending = plan.pending_geography_clarification

    assert plan.requires_clarification is True
    assert plan.resolved_geography_intent() is None
    assert plan.geography.reason_code == "GEOGRAPHY_AMBIGUOUS"
    assert pending is not None
    assert pending.retrieved_candidate_ids == [area.candidate_id for area in AMBIGUOUS_AREAS[place]]
    assert [option.label for option in pending.options] == [area.label for area in AMBIGUOUS_AREAS[place]]
    assert result.get("geo") is None
    assert any(item.collection_name == "census_tables" and item.status == "hit" for item in plan.retrieval_evidence)


def test_unknown_place_fails_closed_without_inventing_an_option_or_us_default():
    fake = ClarificationChromaFake([], status="empty")
    result = _run("Show total population for counties in Atlantis in 2023", fake)
    plan = result["plan"]
    pending = plan.pending_geography_clarification

    assert plan.requires_clarification is True
    assert plan.geography.reason_code == "GEOGRAPHY_NOT_FOUND"
    assert pending is not None
    assert pending.options == []
    assert pending.retrieved_candidate_ids == []
    assert result.get("geo") is None
    assert '"us"' not in result["final"]["answer_text"].lower()


def test_low_confidence_place_fails_closed_and_preserves_retrieved_candidate():
    low = AreaSpec("area:low-confidence", "Uncertain official match", "state", "36", 0.1)
    fake = ClarificationChromaFake([low])
    result = _run("Show total population for counties in uncertain place in 2023", fake)
    plan = result["plan"]
    pending = plan.pending_geography_clarification

    assert plan.requires_clarification is True
    assert plan.geography.reason_code == "GEOGRAPHY_NOT_FOUND"
    assert pending is not None
    assert pending.retrieved_candidate_ids == [low.candidate_id]
    assert [option.label for option in pending.options] == [low.label]
    assert result.get("geo") is None
