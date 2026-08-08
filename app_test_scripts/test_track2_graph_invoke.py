import uuid
from unittest.mock import patch

from app import create_census_graph
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from config import LATEST_AVAILABLE_YEAR
from src.domain.comparison_artifacts import ComparisonInputRow
from src.domain.geography_contract import GeographyIntent
from src.state.types import CensusState, coerce_geography_intent
from src.state.workflow_plan import WorkflowPlan


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


def test_graph_invoke_comparison_path_with_stubbed_agent():
    graph = create_census_graph()
    latest_year = LATEST_AVAILABLE_YEAR

    latest_year = LATEST_AVAILABLE_YEAR
    stub_result = {
        "answer_text": f"County population comparison for {latest_year}.",
        "census_data": {
            "success": True,
            "data": [
                ["year", "geo_id", "population"],
                [latest_year, "06001", 100000],
                [latest_year, "06002", 90000],
            ],
        },
        "data_summary": f"Population data for counties in {latest_year}.",
        "reasoning_trace": "stubbed",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": [],
        "comparison_input_rows": [
            ComparisonInputRow(
                year=latest_year,
                geo_id="06001",
                metric="population",
                value=100000.0,
                benchmark_value=90000.0,
            ),
            ComparisonInputRow(
                year=latest_year,
                geo_id="06002",
                metric="population",
                value=90000.0,
                benchmark_value=100000.0,
            ),
        ],
    }

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = stub_result
        final_state = graph.invoke(
            _state("compare population for counties"),
            config={
                "configurable": {
                    "user_id": "track2-graph-test",
                    "thread_id": f"track2-graph-test-{uuid.uuid4()}",
                    "grounded_geography_dependencies": FakeGroundedRetrieval().dependencies(),
                }
            },
        )

    assert isinstance(final_state["plan"], WorkflowPlan)
    assert final_state["plan"].requires_clarification is False
    assert final_state["plan"].comparison is not None
    assert final_state["plan"].comparison.metric == "population"
    assert final_state["artifacts"].get("comparison_input_rows")
    assert final_state["artifacts"].get("comparison_metrics")
    assert len(final_state["artifacts"]["comparison_metrics"]) >= 1


def test_graph_invoke_exposes_typed_geo_for_resolved_geography():
    graph = create_census_graph()

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = {
            "answer_text": "California population in 2020 was 39.5 million.",
            "census_data": {"success": True, "data": [["population", "39500000"]]},
            "data_summary": "Population data for California in 2020.",
            "reasoning_trace": "stubbed",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }
        final_state = graph.invoke(
            _state("population of california in 2020"),
            config={
                "configurable": {
                    "user_id": "track2-graph-test",
                    "thread_id": f"track2-geo-test-{uuid.uuid4()}",
                    "grounded_geography_dependencies": FakeGroundedRetrieval().dependencies(),
                }
            },
        )

    geo = coerce_geography_intent(final_state.get("geo"))
    assert isinstance(geo, GeographyIntent)
    assert geo.geo_for == {"county": "*"}
    assert geo.geo_in == {"state": "06"}
    assert geo.source == "chroma"
