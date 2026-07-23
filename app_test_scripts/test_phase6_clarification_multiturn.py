"""Phase 6 checkpoint-independent multi-turn clarification behavior."""

from __future__ import annotations

from app_test_scripts.phase6_clarification_fakes import AMBIGUOUS_AREAS, ClarificationChromaFake
from src.services.geography_clarification_resume import resume_geography_clarification
from src.services.graph_session import build_fresh_thread_state
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _pending_plan(place: str):
    question = f"Show total population for counties in {place} in 2023"
    state = build_fresh_thread_state(question)
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    fake = ClarificationChromaFake(AMBIGUOUS_AREAS[place])
    return geography_node(state, {}, dependencies=fake.dependencies())["plan"]


def test_follow_up_selects_only_a_preserved_springfield_candidate_id():
    plan = _pending_plan("Springfield")
    trace_id = plan.retrieval_trace.trace_id
    resumed = resume_geography_clarification(plan, "Springfield, Illinois")

    assert resumed.status == "resolved"
    assert resumed.geography.geo_for == {"county": "*"}
    assert resumed.geography.geo_in == {"state": "17"}
    assert resumed.plan.grounded_plan.geography.area_candidate_ids == ["area:springfield-il"]
    assert resumed.plan.retrieval_trace.trace_id == trace_id
    assert resumed.plan.pending_geography_clarification is None


def test_unknown_follow_up_keeps_original_portland_options_and_trace():
    plan = _pending_plan("Portland")
    pending = plan.pending_geography_clarification
    resumed = resume_geography_clarification(plan, "Portland, Washington")

    assert resumed.status == "clarification_required"
    assert resumed.geography is None
    assert resumed.plan.pending_geography_clarification == pending
    assert resumed.plan.retrieval_trace.trace_id == pending.trace_id


def test_cancel_clears_new_york_pending_context_without_selecting_a_candidate():
    plan = _pending_plan("New York")
    candidate_ids = plan.pending_geography_clarification.retrieved_candidate_ids
    cancelled = resume_geography_clarification(plan, "cancel")

    assert candidate_ids == ["area:new-york-state", "area:new-york-city"]
    assert cancelled.status == "cancelled"
    assert cancelled.geography is None
    assert cancelled.plan.pending_geography_clarification is None
    assert cancelled.plan.workflow_cancelled is True
    assert cancelled.plan.grounded_plan is None
