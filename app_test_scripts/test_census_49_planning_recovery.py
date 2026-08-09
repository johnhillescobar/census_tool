"""CENSUS-49 — planning retry injects validator feedback and merges evidence."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app_test_scripts.test_grounded_census_services import area, evidence, hierarchy, table
from src.agents.census_query_agent import CensusQueryAgent
from src.domain.retrieval_plan import ValidationFailure
from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.llm.prompts.planning_agent import build_planning_agent_prompt
from src.services.agent_plan_context import (
    build_agent_planning_context,
    format_planning_retry_directives,
)
from src.services.agent_planning_artifacts import merge_retrieval_evidence
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.agent_planning import agent_planning_node


def _temporal_plan(**updates) -> WorkflowPlan:
    plan = WorkflowPlan(
        temporal=TemporalResolved(
            time=TemporalIntent(
                mode="point_in_time",
                anchor_year=2023,
                requested_text="population in California",
            )
        ),
        requires_clarification=False,
    )
    if updates:
        return plan.model_copy(update=updates)
    return plan


def _grounded_evidence_bundle():
    table_evidence = evidence("tables", table())
    hierarchy_evidence = evidence("hierarchies", hierarchy())
    area_evidence = evidence("areas", area())
    return [table_evidence, hierarchy_evidence, area_evidence]


def test_build_agent_planning_context_includes_validator_failures_and_prior_evidence():
    failures = [
        ValidationFailure(
            reason_code="UNKNOWN_CANDIDATE_ID",
            message="selected_table_ids references unknown candidate",
            field_path="selected_table_ids",
            candidate_id="table:missing",
            retryable=True,
        )
    ]
    prior = _grounded_evidence_bundle()
    plan = _temporal_plan(
        plan_validation_failures=failures,
        plan_validation_attempts=1,
        retrieval_evidence=prior,
    )

    context = build_agent_planning_context(plan)
    assert context is not None
    assert context.plan_validation_attempt == 1
    assert len(context.plan_validation_failures) == 1
    assert context.plan_validation_failures[0].reason_code == "UNKNOWN_CANDIDATE_ID"
    assert {item.evidence_id for item in context.prior_retrieval_evidence} == {"tables", "hierarchies", "areas"}


def test_format_planning_retry_directives_includes_structured_failure_fields():
    prior = _grounded_evidence_bundle()
    plan = _temporal_plan(
        plan_validation_failures=[
            ValidationFailure(
                reason_code="UNKNOWN_CANDIDATE_ID",
                message="selected_table_ids references unknown candidate",
                field_path="selected_table_ids",
                candidate_id="table:missing",
                evidence_id="tables",
                retryable=True,
            )
        ],
        plan_validation_attempts=1,
        retrieval_evidence=prior,
    )
    context = build_agent_planning_context(plan)
    assert context is not None

    directives = format_planning_retry_directives(context)
    assert "UNKNOWN_CANDIDATE_ID" in directives
    assert "field_path=selected_table_ids" in directives
    assert "candidate_id=table:missing" in directives
    assert "evidence_id=tables" in directives
    assert "evidence_id=tables collection=" in directives
    assert "do not invent candidate IDs" in directives


def test_planning_agent_prompt_describes_validator_retry_behavior():
    prompt = build_planning_agent_prompt(["table_catalog_retrieval", "propose_grounded_plan"])
    assert "validator retry" in prompt.lower()
    assert "validationfailure" in prompt.lower().replace(" ", "")
    assert "preserved" in prompt.lower()


@patch("src.agents.census_query_agent.build_agent_backend")
@patch("src.agents.census_query_agent.create_llm", return_value=MagicMock())
def test_planning_retry_injects_validator_feedback_into_agent_input(mock_llm, mock_backend, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured_input: dict[str, str] = {}

    def _invoke(user_input: str):
        captured_input["text"] = user_input
        execution = MagicMock()
        execution.output = "retry planning summary"
        execution.intermediate_steps = []
        return execution

    mock_backend.return_value.invoke.side_effect = _invoke

    failures = [
        ValidationFailure(
            reason_code="UNKNOWN_CANDIDATE_ID",
            message="selected_table_ids references unknown candidate",
            field_path="selected_table_ids",
            candidate_id="table:missing",
            retryable=True,
        )
    ]
    plan = _temporal_plan(
        plan_validation_failures=failures,
        plan_validation_attempts=1,
        retrieval_evidence=_grounded_evidence_bundle(),
    )
    context = build_agent_planning_context(plan)
    assert context is not None

    agent = CensusQueryAgent(mode="planning", allow_offline=False)
    agent.solve(user_query="population of California in 2023", intent={"is_census": True}, plan_context=context)

    user_input = captured_input["text"]
    assert "Planning retry context" in user_input
    assert "UNKNOWN_CANDIDATE_ID" in user_input
    assert "field_path=selected_table_ids" in user_input
    assert "evidence_id=tables" in user_input


def test_merge_retrieval_evidence_unions_by_evidence_id():
    first = _grounded_evidence_bundle()
    replacement = evidence("tables", table(candidate_id="table:replacement", name="Replacement table"))
    merged = merge_retrieval_evidence(first, [replacement])

    assert len(merged) == 3
    by_id = {item.evidence_id: item for item in merged}
    assert by_id["tables"].candidates[0].candidate_id == "table:replacement"
    assert by_id["hierarchies"].evidence_id == "hierarchies"
    assert by_id["areas"].evidence_id == "areas"


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_node_merges_retrieval_evidence_on_retry(mock_agent_cls):
    prior = _grounded_evidence_bundle()
    new_area = evidence("areas-v2", area(candidate_id="area:nyc"))
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Planning tool steps: 1 (resolve_area_name)",
        "data_summary": "Resolved NYC area evidence.",
        "answer_text": "Retry with NYC area evidence.",
        "intermediate_steps": [
            (
                MagicMock(tool="resolve_area_name"),
                new_area.model_dump(),
            )
        ],
    }

    plan = _temporal_plan(
        plan_validation_failures=[
            ValidationFailure(
                reason_code="PARENT_GEOGRAPHY_INCOMPLETE",
                message="parent geography incomplete for place query",
                field_path="selected_area_ids",
                retryable=True,
            )
        ],
        plan_validation_attempts=1,
        retrieval_evidence=prior,
    )
    state = CensusState(
        messages=[{"role": "user", "content": "population of New York City in 2023"}],
        plan=plan,
    )

    result = agent_planning_node(state, config={})
    updated_plan = result["plan"]

    evidence_ids = {item.evidence_id for item in updated_plan.retrieval_evidence}
    assert evidence_ids == {"tables", "hierarchies", "areas", "areas-v2"}
    _, kwargs = mock_agent_cls.return_value.solve.call_args
    retry_context = kwargs["plan_context"]
    assert retry_context.plan_validation_failures[0].reason_code == "PARENT_GEOGRAPHY_INCOMPLETE"
    assert len(retry_context.prior_retrieval_evidence) == 3
