"""Increment 3 tests: agent-owned clarification authority (CENSUS-44)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.services.agent_plan_context import build_agent_clarification_context, format_clarification_directives
from src.services.clarification_selection import ClarificationSelection, extract_clarification_selection
from src.services.geography_clarification_resume import (
    prepare_table_resume_by_candidate_id,
    render_pending_clarification_retry,
)
from src.services.graph_session import build_fresh_thread_state
from src.workflows.agent_clarification_resume import agent_clarification_resume_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _pending_state():
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    turn1 = geography_node(state, {}, dependencies=AmbiguousTablesFake().dependencies())
    return state.model_copy(update={"plan": turn1["plan"], "final": turn1["final"]})


def _tool_step(option_index: int = 0):
    state = _pending_state()
    pending = state.plan.pending_geography_clarification
    assert pending is not None
    option = pending.options[option_index]
    payload = (
        f'{{"status": "accepted", "option_id": "{option.option_id}", '
        f'"candidate_id": "{option.candidate_id}", "label": "{option.label}"}}'
    )
    return (MagicMock(tool="select_clarification_option"), payload)


def test_extract_clarification_selection_returns_structured_selection():
    agent_result = {"intermediate_steps": [_tool_step(1)]}
    selection = extract_clarification_selection(agent_result)
    assert isinstance(selection, ClarificationSelection)
    assert selection.option_id == "table_1"
    assert selection.candidate_id.endswith("B01002")


def test_prepare_table_resume_by_candidate_id_skips_free_text_parser():
    state = _pending_state()
    plan = state.plan
    pending = plan.pending_geography_clarification
    assert pending is not None
    target = pending.options[0]
    resolved = prepare_table_resume_by_candidate_id(plan, target.candidate_id)
    assert hasattr(resolved, "selected_table")
    assert resolved.selected_table.table_code == "B01001"


def test_render_pending_clarification_retry_uses_readable_labels_not_table_n():
    state = _pending_state()
    retry = render_pending_clarification_retry(
        state.plan,
        "That selection does not match one of the retrieved options.",
    )
    assert "table_0:" not in retry.answer_text
    assert "SEX BY AGE (B01001)" in retry.answer_text


def test_format_clarification_directives_prefers_candidate_id():
    state = _pending_state()
    context = build_agent_clarification_context(state.plan)
    assert context is not None
    directives = format_clarification_directives(context)
    assert "candidate_id=" in directives
    assert "table_0:" not in directives


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_turn2_rejects_raw_user_text_without_tool_selection(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "No tool call",
        "data_summary": "Could not map reply",
        "answer_text": "Please clarify.",
        "intermediate_steps": [],
    }
    fake = AmbiguousTablesFake()
    state = _pending_state()
    resume_state = state.model_copy(
        update={"messages": [{"role": "user", "content": "the second one please"}]}
    )
    config = {"configurable": {"grounded_geography_dependencies": fake.dependencies()}}
    turn2 = agent_clarification_resume_node(resume_state, config)

    assert turn2["plan"].requires_clarification is True
    assert turn2["plan"].pending_geography_clarification is not None
    assert "could not map your reply" in turn2["final"]["answer_text"].casefold()
    assert "table_0:" not in turn2["final"]["answer_text"]


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_turn2_applies_candidate_id_from_tool_without_geography_resume_parser(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Clarification tool steps: 1 (select_clarification_option)",
        "data_summary": "Mapped reply via candidate_id.",
        "answer_text": "Proceeding with SEX BY AGE.",
        "intermediate_steps": [_tool_step(0)],
    }
    fake = AmbiguousTablesFake()
    state = _pending_state()
    resume_state = state.model_copy(
        update={"messages": [{"role": "user", "content": "use the recommended table"}]}
    )
    config = {"configurable": {"grounded_geography_dependencies": fake.dependencies()}}
    turn2 = agent_clarification_resume_node(resume_state, config)
    resumed = turn2["plan"]

    assert resumed.requires_clarification is False
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"
    assert turn2["artifacts"]["clarification_selection"]["candidate_id"].endswith("B01001")
