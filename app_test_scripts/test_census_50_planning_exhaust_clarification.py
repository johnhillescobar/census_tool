"""CENSUS-50 — agent clarification when plan validation retries exhaust."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import app
from app import _route_after_agent_planning, _route_after_plan_validator
from app_test_scripts.test_grounded_census_services import area, evidence, hierarchy, table
from src.domain.geography_catalog import TableCandidate
from src.domain.retrieval_plan import RetrievalEvidence, ValidationFailure
from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.services.graph_session import build_fresh_thread_state
from src.services.grounded_census_planner import select_grounded_plan
from src.services.plan_validation_exhaust_clarification import (
    PLAN_VALIDATION_EXHAUST_PREFIX,
    apply_plan_validation_exhaust_selection,
    is_plan_validation_exhaust_pending,
    prepare_plan_validation_exhaust_clarification,
)
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.agent_clarification_resume import agent_clarification_resume_node
from src.workflows.agent_planning import agent_planning_node
from src.workflows.plan_validation_exhaust import plan_validation_exhaust_node
from src.workflows.plan_validator import MAX_PLAN_VALIDATION_ATTEMPTS, validate_grounded_plan_node


def _temporal_plan(**updates) -> WorkflowPlan:
    plan = WorkflowPlan(
        temporal=TemporalResolved(
            time=TemporalIntent(
                mode="point_in_time",
                anchor_year=2023,
                requested_text="population of New York City",
            )
        ),
        requires_clarification=False,
    )
    if updates:
        return plan.model_copy(update=updates)
    return plan


def _ambiguous_table_evidence():
    population_table = table(candidate_id="table:pop", name="Total Population")
    age_table = TableCandidate(
        candidate_id="table:age",
        dataset="acs/acs5",
        year=2023,
        display_name="Sex By Age",
        score=0.88,
        provenance="census_groups",
        schema_version="1.0",
        table_code="B01001",
        table_name="Sex By Age",
        category="detail",
        years_available=[2023],
    )
    table_bundle = RetrievalEvidence(
        evidence_id="tables",
        collection_name="tables",
        status="hit",
        query_text="population",
        schema_version="1.0",
        index_version="1.0",
        candidate_ids=[population_table.candidate_id, age_table.candidate_id],
        candidates=[population_table, age_table],
    )
    return [table_bundle, evidence("hierarchies", hierarchy()), evidence("areas", area())]


def _exhausted_plan(*, evidence_items=None):
    evidence_items = evidence_items or _ambiguous_table_evidence()
    geo = GeographyRetrievalResult(
        hierarchy_evidence=evidence_items[1],
        area_evidence=[evidence_items[2]],
    )
    selection = select_grounded_plan(evidence_items[0], geo)
    bad_selection = selection.model_copy(update={"selected_table_ids": ["table:missing"]})
    return _temporal_plan(
        proposed_selection=bad_selection,
        retrieval_evidence=evidence_items,
        plan_validation_attempts=MAX_PLAN_VALIDATION_ATTEMPTS,
        plan_validation_failures=[
            ValidationFailure(
                reason_code="UNKNOWN_CANDIDATE_ID",
                message="selected_table_ids references unknown candidate",
                field_path="selected_table_ids",
                candidate_id="table:missing",
                retryable=True,
            )
        ],
    )


def test_plan_validation_exhaust_builds_pending_clarification_from_evidence():
    plan = _exhausted_plan()
    update = prepare_plan_validation_exhaust_clarification(plan, original_query="population of New York City")
    pending = update["plan"].pending_geography_clarification

    assert pending is not None
    assert is_plan_validation_exhaust_pending(pending)
    assert pending.reason_code.startswith(PLAN_VALIDATION_EXHAUST_PREFIX)
    assert pending.requested_slot == "table"
    assert len(pending.options) >= 2
    assert {option.candidate_id for option in pending.options}.issubset({"table:pop", "table:age"})


def test_plan_validation_exhaust_falls_back_when_preferred_slot_has_no_candidates():
    table_bundle = _ambiguous_table_evidence()[0]
    plan = _temporal_plan(
        retrieval_evidence=[table_bundle],
        plan_validation_attempts=MAX_PLAN_VALIDATION_ATTEMPTS,
        plan_validation_failures=[
            ValidationFailure(
                reason_code="UNKNOWN_EVIDENCE_ID",
                message="Selection evidence ID was not supplied by retrieval evidence",
                field_path="evidence_ids",
                evidence_id="bundle:missing",
                retryable=True,
            )
        ],
    )

    update = prepare_plan_validation_exhaust_clarification(plan, original_query="population in California")
    pending = update["plan"].pending_geography_clarification

    assert pending is not None
    assert pending.requested_slot == "table"
    assert len(pending.options) >= 2


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_plan_validation_exhaust_emits_non_empty_clarification_copy(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = True
    plan = _exhausted_plan()
    state = CensusState(
        messages=[{"role": "user", "content": "population of New York City in 2023"}],
        plan=plan,
    )

    exhaust = plan_validation_exhaust_node(state, {})
    state = state.model_copy(update={"plan": exhaust["plan"]})
    clarify = agent_planning_node(state, {})

    assert clarify["final"]["answer_text"]
    assert "table_0:" not in clarify["final"]["answer_text"]
    assert _route_after_agent_planning(state.model_copy(update={"final": clarify["final"]})) == "output"


def test_plan_validation_exhaust_resume_applies_grounded_selection():
    plan = _exhausted_plan()
    prepared = prepare_plan_validation_exhaust_clarification(plan, original_query="population of New York City")
    pending_plan = prepared["plan"]
    target = pending_plan.pending_geography_clarification.options[0]

    resolved = apply_plan_validation_exhaust_selection(pending_plan, target.candidate_id)
    assert resolved.plan.proposed_selection is not None
    assert resolved.plan.pending_geography_clarification is None
    assert resolved.plan.requires_clarification is False
    assert target.candidate_id in resolved.plan.proposed_selection.selected_table_ids

    state = build_fresh_thread_state("population of New York City in 2023").model_copy(update={"plan": resolved.plan})
    validation = validate_grounded_plan_node(state, {})
    assert validation["plan"].grounded_plan is not None


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_plan_validation_exhaust_two_turn_offline_flow(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = False

    def _tool_step(option):
        payload = (
            f'{{"status": "accepted", "option_id": "{option.option_id}", '
            f'"candidate_id": "{option.candidate_id}", "label": "{option.label}"}}'
        )
        return (MagicMock(tool="select_clarification_option"), payload)

    plan = _exhausted_plan()
    prepared = prepare_plan_validation_exhaust_clarification(plan, original_query="population of New York City")
    pending_plan = prepared["plan"]
    option = pending_plan.pending_geography_clarification.options[0]
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Clarification tool steps: 1 (select_clarification_option)",
        "data_summary": "Mapped reply via candidate_id.",
        "answer_text": "Proceeding with grounded area selection.",
        "intermediate_steps": [_tool_step(option)],
    }

    turn1_state = CensusState(
        messages=[{"role": "user", "content": "population of New York City in 2023"}],
        plan=pending_plan,
    )
    turn1 = agent_planning_node(turn1_state, {})
    assert turn1["final"]["answer_text"]

    turn2_state = turn1_state.model_copy(
        update={
            "plan": turn1["plan"],
            "messages": [{"role": "user", "content": option.option_id}],
        }
    )
    turn2 = agent_clarification_resume_node(turn2_state, {})
    resumed_plan = turn2["plan"]

    assert resumed_plan.proposed_selection is not None
    assert resumed_plan.requires_clarification is False
    assert app._route_after_geography(
        turn2_state.model_copy(update={"plan": resumed_plan})
    ) == "plan_validator"

    validated = validate_grounded_plan_node(
        turn2_state.model_copy(update={"plan": resumed_plan}),
        {},
    )
    assert validated["plan"].grounded_plan is not None
    assert _route_after_plan_validator(
        turn2_state.model_copy(update={"plan": validated["plan"], "geo": validated.get("geo")})
    ) == "benchmark"
