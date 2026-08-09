from unittest.mock import patch

from app import _route_after_agent_planning, _route_after_temporal
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.services.graph_session import build_fresh_thread_state
from src.workflows.agent_planning import agent_planning_node
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def test_route_after_temporal_goes_to_agent_planning():
    state = build_fresh_thread_state("population of california")
    temporal_result = temporal_node(state, {})
    temporal_state = state.model_copy(update={"plan": temporal_result["plan"]})
    assert _route_after_temporal(temporal_state) == "agent_planning"


def test_route_after_agent_planning_goes_to_plan_validator():
    state = build_fresh_thread_state("population of california")
    temporal_result = temporal_node(state, {})
    temporal_state = state.model_copy(update={"plan": temporal_result["plan"]})
    assert _route_after_agent_planning(temporal_state) == "plan_validator"


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_turn1_table_ambiguity_reaches_agent_planning_before_geography_halt(mock_agent_cls):
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Planning tool steps: 1 (table_search)",
        "data_summary": "Two population-related tables found.",
        "answer_text": "Table choice is ambiguous; recommend B01003.",
    }
    fake = AmbiguousTablesFake()
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})

    planning = agent_planning_node(state, {})
    state = state.model_copy(
        update={
            "artifacts": planning.get("artifacts", {}),
            "logs": planning.get("logs", []),
        }
    )
    geography = geography_node(state, {}, dependencies=fake.dependencies())

    mock_agent_cls.assert_called_once_with(mode="planning")
    assert planning["logs"] == ["agent_planning: completed retrieval planning turn"]
    assert geography["plan"].requires_clarification is True
    assert geography["plan"].pending_geography_clarification is not None
    assert geography["plan"].pending_geography_clarification.requested_slot == "table"
