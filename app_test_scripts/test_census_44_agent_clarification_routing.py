"""Routing tests for CENSUS-44 agent clarification resume."""

from app import _route_after_memory
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.services.graph_session import build_fresh_thread_state
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _pending_state():
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    turn1 = geography_node(state, {}, dependencies=AmbiguousTablesFake().dependencies())
    return state.model_copy(update={"plan": turn1["plan"]})


def test_route_after_memory_agent_clarification_when_flag_enabled(monkeypatch):
    monkeypatch.setenv("CENSUS_AGENT_CLARIFICATION_RESUME", "1")
    import config

    monkeypatch.setattr(config, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    import app

    monkeypatch.setattr(app, "CENSUS_AGENT_CLARIFICATION_RESUME", True)
    state = _pending_state()
    assert app._route_after_memory(state) == "agent_clarification_resume"


def test_route_after_memory_geography_resume_when_flag_disabled(monkeypatch):
    import app
    import config

    monkeypatch.setattr(config, "CENSUS_AGENT_CLARIFICATION_RESUME", False)
    monkeypatch.setattr(app, "CENSUS_AGENT_CLARIFICATION_RESUME", False)
    state = _pending_state()
    assert _route_after_memory(state) == "geography_resume"
