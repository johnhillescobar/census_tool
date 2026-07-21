import pytest
from langchain_core.runnables import RunnableConfig

from app import _route_after_geography
from src.domain.geography_contract import GeographyIntent, GeographyResolved
from src.services.geography_policy import resolve_geography_intent
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node

CONFIG: RunnableConfig = {"configurable": {"user_id": "test", "thread_id": "test"}}


@pytest.fixture(autouse=True)
def _use_deprecated_geography_policy(monkeypatch):
    monkeypatch.setenv("CENSUS_CHROMA_GROUNDED_PLANNING", "0")


def _state(question: str) -> CensusState:
    return CensusState(
        messages=[{"role": "user", "content": question}],
        original_query=question,
        intent=None,
        plan=None,
        final=None,
        error=None,
        summary=None,
    )


def test_missing_geography_defaults_to_united_states():
    resolution = resolve_geography_intent("Show me median income trends from 2015 to 2020")
    assert resolution.status == "resolved"
    assert resolution.geography.geo_for == {"us": "1"}
    assert resolution.geography.source == "missing_geo_default"


def test_explicit_california_does_not_default_to_us():
    resolution = resolve_geography_intent("population of california")
    assert resolution.status == "resolved"
    assert resolution.geography.level == "state"
    assert resolution.geography.geo_for == {"state": "06"}


def test_invalid_explicit_geography_clarifies():
    resolution = resolve_geography_intent("population of Mars")
    assert resolution.status == "clarification_required"


def test_legacy_geography_node_routes_to_benchmark_when_resolved():
    state = _state("population of california")
    result = geography_node(state, CONFIG)
    assert isinstance(result["plan"], WorkflowPlan)
    assert result["plan"].requires_clarification is False
    assert isinstance(result["plan"].geography, GeographyResolved)
    assert isinstance(result["geo"], GeographyIntent)
    assert result["geo"].geo_for == {"state": "06"}
    assert result["geo"].requested_text is not None
    routed = _route_after_geography(state.model_copy(update={"plan": result["plan"]}))
    assert routed == "benchmark"


def test_geography_node_uses_profile_default_when_geography_missing():
    state = _state("Show me median income trends from 2015 to 2020").model_copy(
        update={
            "profile": {
                "default_geo": {
                    "level": "state",
                    "filters": {"for": "state:48"},
                    "note": "Texas",
                }
            }
        }
    )
    result = geography_node(state, CONFIG)
    assert result["geo"].geo_for == {"state": "48"}
    assert result["geo"].source == "profile_default"


def test_geography_then_temporal_preserves_geography():
    question = "Show me median income trends from 2015 to 2020"
    state = _state(question)
    geo_result = geography_node(state, CONFIG)
    state = state.model_copy(update={"plan": geo_result["plan"], "geo": geo_result["geo"]})
    temporal_result = temporal_node(state, CONFIG)
    assert temporal_result["plan"].geography is not None
    assert temporal_result["plan"].temporal is not None
    assert temporal_result["plan"].temporal.time.start_year == 2015
    assert temporal_result["plan"].temporal.time.end_year == 2020
