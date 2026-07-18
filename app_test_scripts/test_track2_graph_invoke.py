from unittest.mock import patch

from app import create_census_graph
from src.domain.comparison_artifacts import ComparisonInputRow
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan


def test_graph_invoke_comparison_path_with_stubbed_agent():
    graph = create_census_graph()

    stub_result = {
        "answer_text": "California and Texas population comparison for 2020.",
        "census_data": {
            "success": True,
            "data": [
                ["year", "geo_id", "population"],
                [2020, "state:06", 39500000],
                [2020, "state:48", 29100000],
            ],
        },
        "data_summary": "Population data for California and Texas in 2020.",
        "reasoning_trace": "stubbed",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": [],
        "comparison_input_rows": [
            ComparisonInputRow(
                year=2020,
                geo_id="state:06",
                metric="population",
                value=39500000.0,
                benchmark_value=29100000.0,
            ),
            ComparisonInputRow(
                year=2020,
                geo_id="state:48",
                metric="population",
                value=29100000.0,
                benchmark_value=39500000.0,
            ),
        ],
    }

    with patch("src.workflows.agent.CensusQueryAgent") as mock_agent_cls:
        mock_agent_cls.return_value.solve.return_value = stub_result
        final_state = graph.invoke(
            CensusState(
                messages=[
                    {
                        "role": "user",
                        "content": "Compare California vs Texas population in 2020",
                    }
                ],
            ),
            config={"configurable": {"thread_id": "track2-graph-test"}},
        )

    assert isinstance(final_state["plan"], WorkflowPlan)
    assert final_state["plan"].requires_clarification is False
    assert final_state["plan"].comparison is not None
    assert final_state["plan"].comparison.metric == "population"
    assert final_state["artifacts"].get("comparison_input_rows")
    assert final_state["artifacts"].get("comparison_metrics")
    assert len(final_state["artifacts"]["comparison_metrics"]) >= 1
