from unittest.mock import patch

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import TemporalIntent
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.agent import agent_reasoning_node


def _build_plan_context() -> AgentPlanContext:
    return AgentPlanContext(
        temporal=TemporalIntent(
            mode="point_in_time",
            start_year=None,
            end_year=None,
            anchor_year=2020,
            requested_text="compare counties",
        ),
        benchmark=BenchmarkIntent(
            benchmark_type="national",
            metric="population",
            subject_geo_level="state",
            subject_geo=["subject:unknown"],
            benchmark_geo_level="nation",
            benchmark_geos=["us:1"],
            comparison_op="difference",
            normalization="none",
            requested_text="compare counties",
        ),
        comparison=ComparisonPlan(
            query_years=[2020],
            dataset="acs/acs5",
            metric="population",
            subject_geo_level="state",
            subject_geos=["subject:unknown"],
            benchmark_geo_level="nation",
            benchmark_geos=["us:1"],
            comparison_op="difference",
            normalization="none",
            missing_year_policy="skip_with_note",
            derived_metrics=["difference"],
            join_keys=["year", "geo_id"],
            requested_text="compare counties",
        ),
        has_comparison_plan=True,
    )


@patch("src.workflows.agent.CensusQueryAgent")
@patch("src.workflows.agent.build_agent_plan_context")
def test_passes_typed_plan_context_to_solve(
    mock_build_context,
    mock_agent_cls,
):
    plan_context = _build_plan_context()
    mock_build_context.return_value = plan_context
    mock_agent = mock_agent_cls.return_value
    mock_agent.solve.return_value = {
        "census_data": {"success": True, "data": []},
        "data_summary": "summary",
        "reasoning_trace": "trace",
        "answer_text": "Population comparison complete.",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": ["Source: Census"],
        "comparison_input_rows": [
            {
                "year": 2020,
                "geo_id": "10001",
                "metric": "population",
                "value": 10.0,
                "benchmark_value": 8.0,
            }
        ],
    }

    state = CensusState(
        messages=[{"role": "user", "content": "compare counties"}],
        plan=WorkflowPlan(requires_clarification=False),
    )
    agent_reasoning_node(state, config={})

    mock_agent.solve.assert_called_once()
    _, kwargs = mock_agent.solve.call_args
    assert kwargs["plan_context"] is plan_context
    assert isinstance(kwargs["plan_context"], AgentPlanContext)


@patch("src.workflows.agent.CensusQueryAgent")
@patch("src.workflows.agent.build_agent_plan_context")
def test_writes_comparison_input_rows_to_artifacts(
    mock_build_context,
    mock_agent_cls,
):
    mock_build_context.return_value = _build_plan_context()
    rows = [
        {
            "year": 2020,
            "geo_id": "10001",
            "metric": "population",
            "value": 10.0,
            "benchmark_value": 8.0,
        }
    ]
    mock_agent_cls.return_value.solve.return_value = {
        "census_data": {"success": True, "data": []},
        "data_summary": "summary",
        "reasoning_trace": "trace",
        "answer_text": "Population comparison complete.",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": ["Source: Census"],
        "comparison_input_rows": rows,
    }

    state = CensusState(
        messages=[{"role": "user", "content": "compare counties"}],
        plan=WorkflowPlan(requires_clarification=False),
    )
    result = agent_reasoning_node(state, config={})

    assert result["artifacts"]["comparison_input_rows"] == rows
