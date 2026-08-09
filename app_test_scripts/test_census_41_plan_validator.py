"""CENSUS-41 — validate_grounded_plan gate after agent planning.

Test case registry (also posted to Jira CENSUS-41):
--------------------------------------------------------------------------------
| Test | Verifies | Expected outcome |
|------|----------|------------------|
| test_route_after_agent_planning_goes_to_plan_validator | Graph routing after temporal+planning | _route_after_agent_planning → "plan_validator" |
| test_plan_validator_skips_when_no_agent_proposal | Validator with no proposed_selection | Skips with log; routes to legacy "geography" |
| test_plan_validator_rejects_invented_candidate_ids | Fail-closed on invented table ID | UNKNOWN_CANDIDATE_ID, retryable, routes to agent_planning |
| test_plan_validator_accepts_grounded_selection_and_skips_geography | Valid agent proposal + evidence | grounded_plan set, B01003, routes to "benchmark" |
| test_plan_validator_exhausted_retries_route_to_output | Max validation attempts exceeded | Routes to "output" (no further retry) |
| test_legacy_geography_still_runs_when_validator_skips | Fallback when agent proposes nothing | geography_node still produces grounded_plan |
| test_agent_planning_populates_proposal_from_tool_steps | agent_planning_node wires tool output | plan.proposed_selection + retrieval_evidence populated |
| test_agent_planning_to_validator_accepts_grounded_flow | End-to-end mocked planning → validator | Validated plan routes to benchmark |
| test_collect_planning_artifacts_merges_evidence_and_selection | Artifact collector unit behavior | Evidence deduped by ID; latest selection kept |
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app import _route_after_agent_planning, _route_after_plan_validator
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from app_test_scripts.test_grounded_census_services import area, evidence, hierarchy, table
from src.domain.retrieval_plan import ValidationFailure
from src.services.agent_planning_artifacts import collect_planning_artifacts
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.services.graph_session import build_fresh_thread_state
from src.services.grounded_census_planner import select_grounded_plan
from src.state.workflow_plan import WorkflowPlan
from src.workflows.agent_planning import agent_planning_node
from src.workflows.geography import geography_node
from src.workflows.plan_validator import MAX_PLAN_VALIDATION_ATTEMPTS, validate_grounded_plan_node
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


def _state_with_proposal(*, invented_table_id: str | None = None):
    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    selection, evidence_items = _grounded_evidence()
    if invented_table_id is not None:
        selection = selection.model_copy(update={"selected_table_ids": [invented_table_id]})
    plan = temporal_result["plan"].model_copy(
        update={
            "proposed_selection": selection,
            "retrieval_evidence": evidence_items,
        }
    )
    return state.model_copy(update={"plan": plan})


def _mock_planning_steps(selection, evidence_items):
    table_payload = json.dumps({"retrieval_evidence": evidence_items[0].model_dump(mode="json")})
    geo_payload = json.dumps(
        {
            "hierarchy_evidence": evidence_items[1].model_dump(mode="json"),
            "area_evidence": [evidence_items[2].model_dump(mode="json")],
        }
    )
    proposal_payload = selection.model_dump_json()
    return [
        (
            SimpleNamespace(tool="table_catalog_retrieval", tool_input='{"query":"population"}'),
            table_payload,
        ),
        (
            SimpleNamespace(tool="geography_discovery", tool_input='{"action":"enumerate_areas"}'),
            geo_payload,
        ),
        (
            SimpleNamespace(tool="propose_grounded_plan", tool_input=proposal_payload),
            json.dumps({"status": "accepted", "proposed_selection": selection.model_dump(mode="json")}),
        ),
    ]


def test_route_after_agent_planning_goes_to_plan_validator():
    state = build_fresh_thread_state("Population in California in 2023")
    temporal_result = temporal_node(state, {})
    temporal_state = state.model_copy(update={"plan": temporal_result["plan"]})
    assert _route_after_agent_planning(temporal_state) == "plan_validator"


def test_plan_validator_skips_when_no_agent_proposal():
    state = build_fresh_thread_state("Population in California in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})
    result = validate_grounded_plan_node(state, {})
    assert result["logs"] == ["plan_validator: skipped (no agent proposal)"]
    assert _route_after_plan_validator(state) == "geography"


def test_plan_validator_rejects_invented_candidate_ids():
    state = _state_with_proposal(invented_table_id="table:does-not-exist")
    result = validate_grounded_plan_node(state, {})
    plan = result["plan"]
    assert plan.grounded_plan is None
    assert plan.proposed_selection is None
    assert plan.plan_validation_failures
    assert plan.plan_validation_failures[0].reason_code == "UNKNOWN_CANDIDATE_ID"
    assert plan.plan_validation_failures[0].retryable is True
    assert plan.plan_validation_attempts == 1
    retry_state = state.model_copy(update={"plan": plan})
    assert _route_after_plan_validator(retry_state) == "agent_planning"


def test_plan_validator_accepts_grounded_selection_and_skips_geography():
    state = _state_with_proposal()
    result = validate_grounded_plan_node(state, {})
    plan = result["plan"]
    assert plan.grounded_plan is not None
    assert plan.selected_table is not None
    assert plan.selected_table.table_code == "B01003"
    assert plan.proposed_selection is None
    assert plan.plan_validation_failures == []
    assert plan.resolved_geography_intent() is not None
    assert plan.resolved_geography_intent().source == "chroma"
    validated_state = state.model_copy(update={"plan": plan, "geo": result.get("geo")})
    assert _route_after_plan_validator(validated_state) == "benchmark"


def test_plan_validator_exhausted_retries_route_to_output():
    selection, evidence_items = _grounded_evidence()
    bad_selection = selection.model_copy(update={"selected_table_ids": ["table:missing"]})
    plan = WorkflowPlan(
        proposed_selection=bad_selection,
        retrieval_evidence=evidence_items,
        plan_validation_attempts=MAX_PLAN_VALIDATION_ATTEMPTS,
        plan_validation_failures=[
            ValidationFailure(
                reason_code="UNKNOWN_CANDIDATE_ID",
                message="retry exhausted",
                retryable=True,
            )
        ],
    )
    state = build_fresh_thread_state("Population in California in 2023").model_copy(update={"plan": plan})
    assert _route_after_plan_validator(state) == "output"


def test_legacy_geography_still_runs_when_validator_skips():
    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})
    skip = validate_grounded_plan_node(state, {})
    assert skip["logs"] == ["plan_validator: skipped (no agent proposal)"]
    fake = FakeGroundedRetrieval()
    geography_result = geography_node(state, {}, dependencies=fake.dependencies())
    assert geography_result["plan"].grounded_plan is not None


def test_collect_planning_artifacts_merges_evidence_and_selection():
    selection, evidence_items = _grounded_evidence()
    collected_evidence, collected_selection = collect_planning_artifacts(_mock_planning_steps(selection, evidence_items))
    assert len(collected_evidence) == 3
    assert {item.evidence_id for item in collected_evidence} == {item.evidence_id for item in evidence_items}
    assert collected_selection == selection


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_populates_proposal_from_tool_steps(mock_agent_cls):
    selection, evidence_items = _grounded_evidence()
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Planning tool steps: 3 (table_catalog_retrieval, geography_discovery, propose_grounded_plan)",
        "data_summary": "Proposed grounded plan for California counties.",
        "intermediate_steps": _mock_planning_steps(selection, evidence_items),
    }
    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})

    result = agent_planning_node(state, {})

    plan = result["plan"]
    assert plan.proposed_selection == selection
    assert len(plan.retrieval_evidence) == 3
    assert "agent_planning: captured grounded selection proposal" in result["logs"]


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_to_validator_accepts_grounded_flow(mock_agent_cls):
    selection, evidence_items = _grounded_evidence()
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Planning tool steps: 3",
        "data_summary": "Grounded proposal ready.",
        "intermediate_steps": _mock_planning_steps(selection, evidence_items),
    }
    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})

    planning_result = agent_planning_node(state, {})
    state = state.model_copy(update={"plan": planning_result["plan"]})
    validator_result = validate_grounded_plan_node(state, {})
    validated_plan = validator_result["plan"]

    assert validated_plan.grounded_plan is not None
    assert validated_plan.selected_table.table_code == "B01003"
    validated_state = state.model_copy(update={"plan": validated_plan, "geo": validator_result.get("geo")})
    assert _route_after_plan_validator(validated_state) == "benchmark"
