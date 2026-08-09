"""CENSUS-41b - validator recovery for live E2E evidence-id mismatches."""

from __future__ import annotations

from app import _route_after_plan_validator
from app_test_scripts.test_grounded_census_services import area, evidence, hierarchy, table
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.services.graph_session import build_fresh_thread_state
from src.services.grounded_census_planner import select_grounded_plan
from src.services.grounded_plan_validator import validate_grounded_plan
from src.workflows.plan_validator import validate_grounded_plan_node
from src.workflows.temporal import temporal_node


def _grounded_evidence():
    table_evidence = evidence("tables", table())
    hierarchy_evidence = evidence("hierarchies", hierarchy())
    area_evidence = evidence("areas", area())
    geo = GeographyRetrievalResult(
        hierarchy_evidence=hierarchy_evidence,
        area_evidence=[area_evidence],
    )
    selection = select_grounded_plan(table_evidence, geo)
    return selection, [table_evidence, hierarchy_evidence, area_evidence]


def _state_with_proposal(*, evidence_ids: list[str] | None = None, extra_evidence: list[RetrievalEvidence] | None = None):
    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    selection, evidence_items = _grounded_evidence()
    if evidence_ids is not None:
        selection = selection.model_copy(update={"evidence_ids": evidence_ids})
    if extra_evidence:
        evidence_items = [*evidence_items, *extra_evidence]
    plan = temporal_result["plan"].model_copy(
        update={
            "proposed_selection": selection,
            "retrieval_evidence": evidence_items,
        }
    )
    return state.model_copy(update={"plan": plan})


def test_unknown_evidence_id_is_retryable_routes_to_agent_planning():
    state = _state_with_proposal(evidence_ids=["tables", "hierarchies", "areas", "bundle:not-collected"])
    result = validate_grounded_plan_node(state, {})
    plan = result["plan"]
    assert plan.grounded_plan is None
    assert plan.proposed_selection is None
    assert plan.plan_validation_failures
    failure = plan.plan_validation_failures[0]
    assert failure.reason_code == "UNKNOWN_EVIDENCE_ID"
    assert failure.retryable is True
    retry_state = state.model_copy(update={"plan": plan})
    assert _route_after_plan_validator(retry_state) == "agent_planning"


def test_subset_evidence_ids_validates_when_candidates_grounded():
    selection, evidence_items = _grounded_evidence()
    unused = evidence(
        "unused-tables",
        table(candidate_id="table:unused", name="Unused table"),
    )
    subset_selection = selection.model_copy(
        update={"evidence_ids": ["tables", "hierarchies", "areas"]},
    )
    result = validate_grounded_plan(
        subset_selection,
        [*evidence_items, unused],
    )
    assert result.status == "valid"
    assert result.plan is not None
    assert result.plan.table.table_code == "B01003"

    state = _state_with_proposal(
        evidence_ids=["tables", "hierarchies", "areas"],
        extra_evidence=[unused],
    )
    node_result = validate_grounded_plan_node(state, {})
    plan = node_result["plan"]
    assert plan.grounded_plan is not None
    assert plan.plan_validation_failures == []
    validated_state = state.model_copy(update={"plan": plan, "geo": node_result.get("geo")})
    assert _route_after_plan_validator(validated_state) == "benchmark"
