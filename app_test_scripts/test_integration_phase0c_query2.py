"""Phase 0c credentialed regression: median income 2015-2020 (Query 2)."""

import os
import uuid

import pytest

from app import create_census_graph
from src.domain.execution_spec import build_execution_spec
from src.services.agent_plan_context import build_agent_plan_context
from src.state.types import CensusState, coerce_geography_intent
from src.workflows.output import is_census_data_renderable

QUERY = "Show me median income trends from 2015 to 2020"

requires_credentials = pytest.mark.skipif(
    not os.getenv("CENSUS_API_KEY") or not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY and CENSUS_API_KEY for Phase 0c Query 2 regression",
)


def _state(question: str) -> CensusState:
    return CensusState(
        messages=[{"role": "user", "content": question}],
        original_query=question,
        intent={"is_census": True, "topic": "general"},
        plan=None,
        final=None,
        error=None,
        summary=None,
    )


@requires_credentials
@pytest.mark.integration
def test_query2_resolves_us_default_and_six_year_plan():
    graph = create_census_graph()
    final_state = graph.invoke(
        _state(QUERY),
        config={
            "configurable": {
                "user_id": "phase0c-query2",
                "thread_id": f"phase0c-query2-{uuid.uuid4()}",
            }
        },
    )

    plan = final_state.get("plan")
    assert plan is not None
    assert plan.requires_clarification is False

    geo = coerce_geography_intent(final_state.get("geo"))
    assert geo is not None
    assert geo.geo_for == {"us": "1"}
    assert geo.source == "missing_geo_default"

    plan_context = build_agent_plan_context(plan)
    assert plan_context is not None
    spec = build_execution_spec(plan_context)
    assert spec is not None
    assert spec.query_years == [2015, 2016, 2017, 2018, 2019, 2020]

    census_data = (final_state.get("artifacts") or {}).get("census_data") or {}
    final = final_state.get("final") or {}
    charts = final.get("charts_needed") or []

    if is_census_data_renderable(census_data):
        assert charts, "Renderable series should request a chart"
        assert charts[0].get("type") == "line"
    else:
        assert charts == [], "Failed/clarification output must not request charts"

    assert final.get("answer_text"), "Expected a non-empty answer"
