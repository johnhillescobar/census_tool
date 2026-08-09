"""CENSUS-44b increment 1: turn-1 ambiguity routes through agent_planning."""

from __future__ import annotations

from unittest.mock import patch

import app
import config
from app import _route_after_agent_planning, _route_after_geography
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.services.graph_session import build_fresh_thread_state
from src.workflows.agent_planning import agent_planning_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _pending_state():
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
