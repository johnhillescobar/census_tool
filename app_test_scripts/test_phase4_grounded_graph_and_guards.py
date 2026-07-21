from __future__ import annotations

import json

from app import _route_after_geography, _route_after_temporal
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.services.graph_session import build_fresh_thread_state
from src.services.grounded_execution_context import (
    GroundedExecutionContext,
    get_grounded_execution_context,
    reset_grounded_execution_context,
    set_grounded_execution_context,
)
from src.tools.census_api_tool import CensusAPITool
from src.tools.strict_census_api_tool import StrictCensusApiTool
from src.workflows.agent import agent_reasoning_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _grounded_state(question: str = "Show total population for all California counties in 2023"):
    state = build_fresh_thread_state(question)
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})
    fake = FakeGroundedRetrieval()
    geography_result = geography_node(state, {}, dependencies=fake.dependencies())
    return state.model_copy(update={"plan": geography_result["plan"], "geo": geography_result.get("geo")}), fake


def test_graph_routes_temporal_before_grounded_geography_then_benchmark():
    state = build_fresh_thread_state("Population in California in 2023")
    temporal_result = temporal_node(state, {})
    temporal_state = state.model_copy(update={"plan": temporal_result["plan"]})
    assert _route_after_temporal(temporal_state) == "geography"

    fake = FakeGroundedRetrieval()
    geography_result = geography_node(temporal_state, {}, dependencies=fake.dependencies())
    geography_state = temporal_state.model_copy(update={"plan": geography_result["plan"]})
    assert _route_after_geography(geography_state) == "benchmark"
    assert [name for name, _value in fake.calls[:3]] == ["analyze", "table", "geography"]


def test_grounded_geography_fails_closed_without_explicit_geography_after_table_retrieval():
    state = build_fresh_thread_state("Show total population in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})
    fake = FakeGroundedRetrieval()
    result = geography_node(state, {}, dependencies=fake.dependencies())

    assert result["plan"].requires_clarification is True
    assert result["plan"].geography.reason_code == "GEOGRAPHY_PARTITION_MISSING"
    assert ("table", 2023) in fake.calls
    assert not any(name == "geography" for name, _value in fake.calls)
    assert result.get("geo") is None


def test_grounded_geography_persists_selected_table_evidence_and_trace():
    state, _fake = _grounded_state()
    plan = state.plan
    assert plan is not None
    assert plan.selected_table is not None
    assert plan.selected_table.table_code == "B01003"
    assert plan.grounded_plan is not None
    assert len(plan.retrieval_evidence) == 3
    assert plan.retrieval_trace is not None
    assert plan.resolved_geography_intent().source == "chroma"


def test_both_census_api_tools_reject_values_outside_validated_plan(monkeypatch):
    state, _fake = _grounded_state()
    assert state.plan is not None and state.plan.grounded_plan is not None
    called = False

    def fail_fetch(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("API fetch must not run")

    monkeypatch.setattr("src.tools.census_api_tool.fetch_census_data", fail_fetch)
    monkeypatch.setattr("src.tools.strict_census_api_tool.fetch_census_data_typed", fail_fetch)
    token = set_grounded_execution_context(GroundedExecutionContext(plan=state.plan.grounded_plan, allowed_years=[2023]))
    try:
        request = {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME", "B01003_001E"],
            "geo_for": {"state": "06"},
            "geo_in": {},
        }
        legacy = json.loads(CensusAPITool()._run(json.dumps(request)))
        strict = StrictCensusApiTool()._run(request)
    finally:
        reset_grounded_execution_context(token)

    assert legacy["success"] is False
    assert legacy["error_type"] == "grounded_plan_guard"
    assert strict.success is False
    assert strict.error == "GROUNDED_PLAN_GUARD_REJECTED"
    assert called is False


def test_agent_solve_runs_inside_grounded_execution_context(monkeypatch):
    state, _fake = _grounded_state()
    observed = []

    class FakeAgent:
        def solve(self, **kwargs):
            observed.append(get_grounded_execution_context())
            return {
                "answer_text": "Grounded California county population result.",
                "census_data": {"success": False, "data": []},
                "data_summary": "Grounded test result.",
                "reasoning_trace": "fake",
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": ["test"],
            }

    monkeypatch.setattr("src.workflows.agent.CensusQueryAgent", FakeAgent)
    agent_reasoning_node(state, {})
    assert observed and observed[0] is not None
    assert observed[0].plan.table.table_code == "B01003"
    assert get_grounded_execution_context() is None
