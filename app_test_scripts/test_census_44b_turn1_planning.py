"""CENSUS-44b increment 1: turn-1 ambiguity routes through agent_planning."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import app
import config
from app import _route_after_agent_planning, _route_after_geography, create_census_graph
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.services.agent_plan_context import build_agent_clarification_context, format_clarification_directives
from src.services.graph_session import build_fresh_thread_state, build_turn_state_for_thread, runnable_config
from src.workflows.agent_planning import agent_planning_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _pending_state(*, monkeypatch=None, turn1_planning: bool = False):
    if turn1_planning and monkeypatch is not None:
        _enable_turn1_planning(monkeypatch)
        import src.workflows.geography as geography_module

        monkeypatch.setattr(geography_module, "CENSUS_AGENT_TURN1_PLANNING", True)
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    turn1 = geography_node(state, {}, dependencies=AmbiguousTablesFake().dependencies())
    return state.model_copy(update={"plan": turn1["plan"], "final": turn1.get("final")})


def _enable_turn1_planning(monkeypatch):
    monkeypatch.setattr(config, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    monkeypatch.setattr(config, "CENSUS_AGENT_TURN1_PLANNING", True)
    monkeypatch.setattr(app, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    monkeypatch.setattr(app, "CENSUS_AGENT_TURN1_PLANNING", True)


def test_route_after_geography_uses_agent_planning_when_turn1_flag_enabled(monkeypatch):
    _enable_turn1_planning(monkeypatch)
    state = _pending_state()
    assert _route_after_geography(state) == "agent_planning"


def test_route_after_agent_planning_exits_to_output_after_turn1_clarify(monkeypatch):
    _enable_turn1_planning(monkeypatch)
    state = _pending_state()
    assert _route_after_agent_planning(state) == "output"


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_agent_planning_node_emits_turn1_clarification_copy(mock_agent_cls, monkeypatch):
    _enable_turn1_planning(monkeypatch)
    mock_agent_cls.return_value.offline_mode = True
    state = _pending_state()

    update = agent_planning_node(state, {})

    assert update["logs"][0] == "agent_planning: turn-1 clarification copy (agent offline)"
    assert "SEX BY AGE (B01001)" in update["final"]["answer_text"]
    assert "table_0:" not in update["final"]["answer_text"]
    assert update["artifacts"]["turn1_planning_authority"] is True


def test_turn1_planning_vertical_slice_routes_geography_to_agent_planning(monkeypatch):
    _enable_turn1_planning(monkeypatch)
    fake = AmbiguousTablesFake()
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})

    geography = geography_node(state, {}, dependencies=fake.dependencies())
    state = state.model_copy(update={"plan": geography["plan"]})

    assert geography["plan"].requires_clarification is True
    assert _route_after_geography(state) == "agent_planning"

    clarify = agent_planning_node(state, {})
    state = state.model_copy(update={"final": clarify["final"], "logs": clarify.get("logs", [])})

    assert _route_after_agent_planning(state) == "output"
    assert "SEX BY AGE (B01001)" in state.final["answer_text"]


def test_geography_defers_final_copy_when_turn1_planning_enabled(monkeypatch):
    _enable_turn1_planning(monkeypatch)
    import src.workflows.geography as geography_module

    monkeypatch.setattr(geography_module, "CENSUS_AGENT_TURN1_PLANNING", True)
    monkeypatch.setattr(geography_module, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    deps = AmbiguousTablesFake().dependencies()
    turn1 = geography_node(
        _pending_state().model_copy(update={"final": None}),
        {},
        dependencies=deps,
    )
    assert turn1.get("final") is None
    assert any("deferred clarification copy" in log for log in turn1.get("logs", []))


def test_geography_emits_final_when_turn1_without_clarification_resume(monkeypatch):
    monkeypatch.setattr(config, "CENSUS_AGENT_TURN1_PLANNING", True)
    monkeypatch.setattr(config, "CENSUS_AGENT_CLARIFICATION_RESUME", False)
    import src.workflows.geography as geography_module

    monkeypatch.setattr(geography_module, "CENSUS_AGENT_TURN1_PLANNING", True)
    monkeypatch.setattr(geography_module, "CENSUS_AGENT_CLARIFICATION_RESUME", False)
    deps = AmbiguousTablesFake().dependencies()
    turn1 = geography_node(
        _pending_state().model_copy(update={"final": None}),
        {},
        dependencies=deps,
    )
    assert turn1.get("final") is not None
    assert turn1["final"]["answer_text"]
    assert not any("deferred clarification copy" in log for log in turn1.get("logs", []))


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_turn1_planning_persists_unified_checkpoint(mock_agent_cls, monkeypatch):
    _enable_turn1_planning(monkeypatch)
    mock_agent_cls.return_value.offline_mode = True
    state = _pending_state(monkeypatch=monkeypatch, turn1_planning=True)

    update = agent_planning_node(state, {})
    plan = update["plan"]

    assert plan.agent_clarification_checkpoint is not None
    assert plan.agent_clarification_checkpoint.turn1_prompt_text is not None
    assert "SEX BY AGE (B01001)" in plan.agent_clarification_checkpoint.turn1_prompt_text

    context = build_agent_clarification_context(plan)
    assert context is not None
    assert context.turn1_prompt_text == plan.agent_clarification_checkpoint.turn1_prompt_text
    directives = format_clarification_directives(context)
    assert "Turn-1 clarification shown to the user:" in directives


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_turn1_planning_two_turn_unified_checkpoint_flow(_mock_agent_cls, monkeypatch, tmp_path):
    _enable_turn1_planning(monkeypatch)
    import src.workflows.geography as geography_module

    monkeypatch.setattr(geography_module, "CENSUS_AGENT_TURN1_PLANNING", True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CENSUS_CHECKPOINT_DB", str(tmp_path / "census44b-unified.db"))
    monkeypatch.setenv("CENSUS_AGENT_TURN1_PLANNING", "1")

    class FakeAgent:
        offline_mode = True

        def __init__(self, mode="execution", allow_offline=True):
            self.mode = mode

        def solve(self, **kwargs):
            clarification_context = kwargs.get("clarification_context")
            if clarification_context is not None:
                option = clarification_context.pending_options[0]
                return {
                    "reasoning_trace": "Clarification tool steps: 1 (select_clarification_option)",
                    "data_summary": f"User selected {option.option_id}.",
                    "answer_text": "Proceeding with grounded table selection.",
                    "intermediate_steps": [
                        (
                            MagicMock(tool="select_clarification_option"),
                            f'{{"status": "accepted", "option_id": "{option.option_id}", '
                            f'"candidate_id": "{option.candidate_id}", "label": "{option.label}"}}',
                        ),
                    ],
                }
            return {
                "reasoning_trace": "planning offline",
                "data_summary": "planning offline",
                "answer_text": "planning offline",
            }

        def compose_clarification_prompt(self, _ctx):
            return {"answer_text": "Which table should I use?\n- SEX BY AGE (B01001) — recommended"}

    monkeypatch.setattr("src.workflows.agent_planning.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent_clarification_resume.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent.CensusQueryAgent", FakeAgent)

    fake = AmbiguousTablesFake()
    graph = create_census_graph()
    config_obj = runnable_config(user_id="census44b-unified", thread_id="census44b-thread")
    config_obj["configurable"]["grounded_geography_dependencies"] = fake.dependencies()

    turn1_state = build_turn_state_for_thread(
        graph,
        "Show total population for all California counties in 2023.",
        config=config_obj,
    )
    turn1 = graph.invoke(turn1_state, config_obj)

    assert turn1["plan"].requires_clarification is True
    assert turn1["plan"].agent_clarification_checkpoint is not None
    assert "SEX BY AGE" in turn1["final"]["answer_text"]
    assert "table_0:" not in turn1["final"]["answer_text"]

    turn2_state = build_turn_state_for_thread(graph, "table_0", config=config_obj)
    turn2 = graph.invoke(turn2_state, config_obj)

    assert turn2["plan"].requires_clarification is False
    assert turn2["plan"].selected_table is not None
    assert turn2["plan"].selected_table.table_code == "B01001"
