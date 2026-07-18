from unittest.mock import patch

from src.domain.geography_contract import GeographyIntent
from src.state.types import (
    CensusState,
    coerce_geography_intent,
    geo_intent_to_dict,
)
from src.workflows.agent import agent_reasoning_node
from src.workflows.memory import memory_write_node


def _state(**overrides) -> CensusState:
    base = {
        "messages": [{"role": "user", "content": "test"}],
        "original_query": "test",
        "intent": None,
        "plan": None,
        "final": None,
        "error": None,
        "summary": None,
    }
    base.update(overrides)
    return CensusState(**base)


def test_coerce_geography_intent_normalizes_empty_dict_to_none():
    assert coerce_geography_intent({}) is None


def test_coerce_geography_intent_accepts_legacy_resolved_dict():
    legacy = {
        "level": "state",
        "geo_for": {"state": "06"},
        "geo_in": {},
        "display_name": "California",
        "source": "explicit",
    }
    geo = coerce_geography_intent(legacy)
    assert isinstance(geo, GeographyIntent)
    assert geo.display_name == "California"


def test_census_state_geo_validator_coerces_legacy_empty_dict():
    state = _state(geo={})
    assert state.geo is None


def test_geo_intent_to_dict_projects_json_for_memory_boundary():
    geo = GeographyIntent(
        level="nation",
        geo_for={"us": "1"},
        geo_in={},
        display_name="United States",
        source="missing_geo_default",
        requested_text="median income trends",
    )
    projected = geo_intent_to_dict(geo)
    assert projected["display_name"] == "United States"
    assert projected["requested_text"] == "median income trends"


@patch("src.workflows.memory.build_history_record")
@patch("src.workflows.memory.update_profile")
@patch("src.workflows.memory.save_json_file", return_value=True)
@patch("src.workflows.memory.enforce_retention_policies")
def test_memory_write_projects_typed_geo_to_dict(
    _mock_enforce,
    _mock_save,
    mock_update_profile,
    mock_build_history,
):
    geo = GeographyIntent(
        level="state",
        geo_for={"state": "06"},
        geo_in={},
        display_name="California",
        source="explicit",
    )
    state = _state(
        messages=[{"role": "user", "content": "population of california"}],
        original_query="population of california",
        geo=geo,
        final={"answer_text": "done"},
        profile={"user_id": "u1"},
        history=[],
        cache_index={},
    )
    memory_write_node(state, {"configurable": {"user_id": "u1"}})
    projected = geo_intent_to_dict(geo)
    mock_build_history.assert_called_once()
    assert mock_build_history.call_args.args[3] == projected
    mock_update_profile.assert_called_once()
    assert mock_update_profile.call_args.args[2] == projected


@patch("src.workflows.agent.generate_llm_answer", return_value="Generated answer text.")
@patch("src.workflows.agent.CensusQueryAgent")
@patch("src.workflows.agent.build_agent_plan_context", return_value=None)
def test_agent_projects_typed_geo_for_short_answer_enrichment(
    _mock_context,
    mock_agent_cls,
    mock_generate,
):
    geo = GeographyIntent(
        level="state",
        geo_for={"state": "06"},
        geo_in={},
        display_name="California",
        source="explicit",
    )
    mock_agent_cls.return_value.solve.return_value = {
        "census_data": {"success": True, "data": [["x"]]},
        "data_summary": "summary",
        "reasoning_trace": "trace",
        "answer_text": "short",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": [],
    }
    state = _state(
        messages=[{"role": "user", "content": "population of california"}],
        original_query="population of california",
        geo=geo,
    )
    agent_reasoning_node(state, config={})
    mock_generate.assert_called_once()
    assert mock_generate.call_args.kwargs["geo_context"]["display_name"] == "California"
