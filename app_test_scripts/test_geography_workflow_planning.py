from langchain_core.runnables import RunnableConfig

from app import _route_after_geography
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.domain.geography_contract import GeographyClarificationRequired, GeographyIntent, GeographyResolved
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


def _config(fake: FakeGroundedRetrieval) -> RunnableConfig:
    return {
        "configurable": {
            "user_id": "test",
            "thread_id": "test",
            "grounded_geography_dependencies": fake.dependencies(),
        }
    }


def _state(question: str) -> CensusState:
    return CensusState(messages=[{"role": "user", "content": question}], original_query=question)


def test_missing_geography_fails_closed_to_clarification():
    fake = FakeGroundedRetrieval()
    result = geography_node(_state("Show me median income trends from 2015 to 2020"), _config(fake))

    assert isinstance(result["plan"].geography, GeographyClarificationRequired)
    assert result["plan"].geography.reason_code == "GEOGRAPHY_PARTITION_MISSING"
    assert "geo" not in result


def test_grounded_geography_routes_to_benchmark_when_resolved():
    state = _state("population by county in California")
    result = geography_node(state, _config(FakeGroundedRetrieval()))

    assert isinstance(result["plan"], WorkflowPlan)
    assert result["plan"].requires_clarification is False
    assert isinstance(result["plan"].geography, GeographyResolved)
    assert isinstance(result["geo"], GeographyIntent)
    assert result["geo"].source == "chroma"
    assert result["geo"].geo_for == {"county": "*"}
    assert result["geo"].geo_in == {"state": "06"}
    assert _route_after_geography(state.model_copy(update={"plan": result["plan"]})) == "benchmark"


def test_unavailable_geography_partition_fails_closed():
    result = geography_node(
        _state("population by county in California"),
        _config(FakeGroundedRetrieval(geography_status="unavailable")),
    )

    assert result["plan"].requires_clarification is True
    assert result["plan"].geography.reason_code == "GEOGRAPHY_INDEX_UNAVAILABLE"
    assert "geo" not in result


def test_profile_default_is_retrieval_input_not_runtime_authority():
    state = _state("Show me median income trends from 2015 to 2020").model_copy(
        update={
            "profile": {
                "default_geo": {
                    "level": "state",
                    "geo_for": {"state": "06"},
                    "display_name": "California",
                }
            }
        }
    )
    result = geography_node(state, _config(FakeGroundedRetrieval()))

    assert result["geo"].source == "chroma"
    assert result["plan"].retrieval_evidence


def test_temporal_then_geography_preserves_temporal_resolution():
    question = "Show county population in California from 2015 to 2020"
    state = _state(question)
    temporal_result = temporal_node(state, _config(FakeGroundedRetrieval()))
    state = state.model_copy(update={"plan": temporal_result["plan"]})
    geography_result = geography_node(state, _config(FakeGroundedRetrieval()))

    assert geography_result["plan"].geography is not None
    assert geography_result["plan"].temporal is not None
    assert geography_result["plan"].temporal.time.start_year == 2015
    assert geography_result["plan"].temporal.time.end_year == 2020
