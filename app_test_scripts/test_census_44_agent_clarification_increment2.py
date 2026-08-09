"""Increment 2 tests: turn-1 agent copy and tool-based turn-2 selection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app import _route_after_geography, create_census_graph
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.services.agent_clarification_copy import build_agent_clarification_copy
from src.services.agent_plan_context import build_agent_clarification_context
from src.services.clarification_selection import extract_clarification_selection
from src.services.graph_session import build_fresh_thread_state, build_turn_state_for_thread, runnable_config
from src.tools.select_clarification_option_tool import SelectClarificationOptionTool
from src.workflows.agent_clarification_prompt import agent_clarification_prompt_node
from src.workflows.agent_clarification_resume import agent_clarification_resume_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _pending_state():
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    turn1 = geography_node(state, {}, dependencies=AmbiguousTablesFake().dependencies())
    return state.model_copy(update={"plan": turn1["plan"], "final": turn1["final"]})


def test_route_after_geography_uses_agent_clarification_prompt_when_flag_enabled(monkeypatch):
    import app
    import config

    monkeypatch.setattr(config, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    monkeypatch.setattr(app, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    state = _pending_state()
    assert _route_after_geography(state) == "agent_clarification_prompt"


def test_build_agent_clarification_copy_uses_readable_labels_and_recommended_default():
    state = _pending_state()
    context = build_agent_clarification_context(state.plan)
    assert context is not None
    copy = build_agent_clarification_copy(context)

    assert "SEX BY AGE (B01001)" in copy
    assert "MEDIAN AGE BY SEX (B01002)" in copy
    assert "recommended default" in copy.casefold()
    assert "table_0:" not in copy


@patch("src.workflows.agent_clarification_prompt.CensusQueryAgent")
def test_agent_clarification_prompt_node_replaces_raw_option_ids(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = True
    state = _pending_state()
    update = agent_clarification_prompt_node(state, {})

    assert "SEX BY AGE (B01001)" in update["final"]["answer_text"]
    assert "table_0:" not in update["final"]["answer_text"]
    assert update["artifacts"]["clarification_prompt_source"] == "deterministic"


def test_select_clarification_option_tool_validates_grounded_option():
    state = _pending_state()
    context = build_agent_clarification_context(state.plan)
    assert context is not None
    tool = SelectClarificationOptionTool()
    tool.bind_context(context)

    accepted = tool.invoke('{"option_id": "table_0"}')
    assert '"status": "accepted"' in accepted
    rejected = tool.invoke('{"option_id": "table_99"}')
    assert '"status": "rejected"' in rejected


def test_extract_clarification_selection_reads_accepted_tool_step():
    agent_result = {
        "intermediate_steps": [
            (MagicMock(tool="select_clarification_option"), '{"status": "accepted", "option_id": "table_1"}'),
        ]
    }
    assert extract_clarification_selection(agent_result) == "table_1"


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_turn2_prefers_agent_tool_selection_over_raw_user_text(mock_agent_cls):
    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Clarification tool steps: 1 (select_clarification_option)",
        "data_summary": "Mapped reply to table_0.",
        "answer_text": "Proceeding with SEX BY AGE.",
        "intermediate_steps": [
            (MagicMock(tool="select_clarification_option"), '{"status": "accepted", "option_id": "table_0"}'),
        ],
    }
    fake = AmbiguousTablesFake()
    state = _pending_state()
    resume_state = state.model_copy(
        update={"messages": [{"role": "user", "content": "the second one please"}]}
    )
    config = {"configurable": {"grounded_geography_dependencies": fake.dependencies()}}
    turn2 = agent_clarification_resume_node(resume_state, config)
    resumed = turn2["plan"]

    assert resumed.requires_clarification is False
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"


def test_checkpoint_graph_turn1_emits_readable_clarification_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CENSUS_CHECKPOINT_DB", str(tmp_path / "census44-inc2.db"))

    class FakeAgent:
        offline_mode = True

        def __init__(self, mode="execution", allow_offline=True):
            self.mode = mode

        def solve(self, **kwargs):
            return {
                "reasoning_trace": "fake",
                "data_summary": "fake",
                "answer_text": "fake",
            }

        def compose_clarification_prompt(self, _ctx):
            return {"answer_text": "Which table should I use?\n- SEX BY AGE (B01001) — recommended"}

    monkeypatch.setattr("src.workflows.agent_clarification_prompt.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent_clarification_resume.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent_planning.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent.CensusQueryAgent", FakeAgent)

    graph = create_census_graph()
    config = runnable_config(user_id="census44-inc2", thread_id="census44-thread")
    config["configurable"]["grounded_geography_dependencies"] = AmbiguousTablesFake().dependencies()

    turn1_state = build_turn_state_for_thread(
        graph,
        "Show total population for all California counties in 2023.",
        config=config,
    )
    turn1 = graph.invoke(turn1_state, config)

    assert turn1["plan"].requires_clarification is True
    assert "SEX BY AGE" in turn1["final"]["answer_text"]
    assert "table_0:" not in turn1["final"]["answer_text"]
