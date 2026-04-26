import pytest
from pydantic import ValidationError

from app import _route_after_benchmark
from src.agents.census_query_agent import AgentOutput
from src.domain.agent_output_contract import AgentSolveResult
from src.domain.benchmark_contract import BenchmarkIntent, BenchmarkResolved
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.state.types import (
    BenchmarkNotApplicable,
    CensusState,
    FinalResponseState,
    WorkflowArtifactsState,
    WorkflowPlanState,
)
from src.tools.geography_validation_tool import GeographyValidationTool
from src.tools.variable_validation_tool import VariableValidationTool
from src.workflows.agent import agent_reasoning_node
from src.workflows.comparison import comparison_node
from src.workflows.comparison_metrics import comparison_metrics_node


def _build_temporal_resolved() -> TemporalResolved:
    return TemporalResolved(
        time=TemporalIntent(
            mode="point_in_time",
            anchor_year=2023,
            requested_text="population in 2023",
        )
    )


def _build_benchmark_resolved() -> BenchmarkResolved:
    return BenchmarkResolved(
        benchmark=BenchmarkIntent(
            benchmark_type="peer_group",
            metric="population",
            subject_geo_level="county",
            subject_geo=["10001", "10002", "10003"],
            benchmark_geo_level="county",
            benchmark_geos=["10001", "10002", "10003"],
            comparison_op="difference",
            normalization="none",
            requested_text="compare population",
        )
    )


def test_comparison_node_preserves_typed_plan_objects():
    state = CensusState(
        messages=[{"content": "Compare county populations"}],
        plan=WorkflowPlanState(
            temporal=_build_temporal_resolved(),
            benchmark=_build_benchmark_resolved(),
            requires_clarification=False,
        ),
    )

    result = comparison_node(state, {})

    assert isinstance(result["plan"], WorkflowPlanState)
    assert isinstance(result["plan"].comparison, ComparisonPlan)
    assert result["plan"].comparison is not None
    assert result["plan"].comparison.query_years == [2023]


def test_comparison_metrics_node_reads_typed_state():
    comparison_result = comparison_node(
        CensusState(
            messages=[{"content": "Compare county populations"}],
            plan=WorkflowPlanState(
                temporal=_build_temporal_resolved(),
                benchmark=_build_benchmark_resolved(),
                requires_clarification=False,
            ),
        ),
        {},
    )
    plan = comparison_result["plan"]

    state = CensusState(
        messages=[{"content": "Compare county populations"}],
        plan=plan,
        artifacts=WorkflowArtifactsState(
            comparison_input_rows=[
                {
                    "year": 2023,
                    "geo_id": "10001",
                    "metric": "population",
                    "value": 10.0,
                    "benchmark_value": 8.0,
                }
            ]
        ),
    )

    result = comparison_metrics_node(state, {})

    assert isinstance(result["artifacts"], WorkflowArtifactsState)
    assert result["artifacts"].comparison_metrics[0].derived_metric == "difference"
    assert result["artifacts"].comparison_metrics[0].value == 2.0


def test_route_after_benchmark_handles_typed_not_applicable_plan():
    state = CensusState(
        messages=[{"content": "Population in California"}],
        plan=WorkflowPlanState(
            temporal=_build_temporal_resolved(),
            benchmark=BenchmarkNotApplicable(reason="no_comparison_intent"),
            requires_clarification=False,
        ),
    )

    assert _route_after_benchmark(state) == "agent"


def test_agent_reasoning_node_returns_typed_final_and_artifacts(monkeypatch):
    class FakeAgent:
        def solve(self, user_query, intent):
            return AgentSolveResult(
                census_data=None,
                data_summary="summary",
                reasoning_trace="trace",
                answer_text="California has a population according to the ACS.",
                charts_needed=[{"type": "bar", "title": "Population by Location"}],
                tables_needed=[
                    {"format": "csv", "filename": "population", "title": "Population"}
                ],
                footnotes=["Source note"],
            )

    monkeypatch.setattr("src.workflows.agent.CensusQueryAgent", FakeAgent)

    result = agent_reasoning_node(
        CensusState(messages=[{"content": "Population in California"}]),
        {},
    )

    assert isinstance(result["artifacts"], WorkflowArtifactsState)
    assert isinstance(result["final"], FinalResponseState)
    assert result["final"].charts_needed[0].type == "bar"
    assert result["final"].charts_needed[0].title == "Population by Location"
    assert result["final"].tables_needed[0].filename == "population"


def test_agent_output_rejects_extra_chart_fields():
    with pytest.raises(ValidationError):
        AgentOutput.model_validate(
            {
                "census_data": {"success": True, "data": [["NAME"], ["California"]]},
                "data_summary": "summary",
                "reasoning_trace": "trace",
                "answer_text": "Population answer",
                "charts_needed": [
                    {
                        "type": "bar",
                        "title": "Population by Location",
                        "x_column": "NAME",
                    }
                ],
                "tables_needed": [],
                "footnotes": ["Source note"],
            }
        )


def test_agent_output_rejects_extra_table_fields():
    with pytest.raises(ValidationError):
        AgentOutput.model_validate(
            {
                "census_data": {"success": True, "data": [["NAME"], ["California"]]},
                "data_summary": "summary",
                "reasoning_trace": "trace",
                "answer_text": "Population answer",
                "charts_needed": [],
                "tables_needed": [
                    {
                        "format": "csv",
                        "filename": "population",
                        "title": "Population",
                        "sheet_name": "Sheet1",
                    }
                ],
                "footnotes": ["Source note"],
            }
        )


def test_planning_tools_expose_strict_args_schema(monkeypatch):
    geography_tool = GeographyValidationTool()
    variable_tool = VariableValidationTool()

    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_and_fix_geo_params",
        lambda dataset, year, geo_for, geo_in, **kwargs: (
            "county",
            "*",
            [("state", "06")],
        ),
    )
    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_geography_hierarchy",
        lambda dataset, year, for_token, provided_parents: (True, [], ""),
    )
    monkeypatch.setattr(
        "src.tools.variable_validation_tool.validate_variables",
        lambda dataset, year, variables: {
            "valid": variables,
            "invalid": [],
            "years_available": {var: [str(year)] for var in variables},
            "details": {
                var: {
                    "concept": "Population",
                    "label": "Population",
                    "universe": "Total population",
                    "dataset": dataset,
                }
                for var in variables
            },
            "alternatives": {},
            "source": {var: "test" for var in variables},
            "warnings": [],
        },
    )

    geography_response = geography_tool._run(
        {
            "dataset": "acs/acs5",
            "year": 2023,
            "geo_for": {"county": "*"},
            "geo_in": {"state": "06"},
        }
    )
    variable_response = variable_tool._run(
        {
            "dataset": "acs/acs5",
            "year": 2023,
            "variables": ["B01003_001E"],
        }
    )

    assert geography_tool.args_schema is not None
    assert variable_tool.args_schema is not None
    assert geography_response.success is True
    assert geography_response.request is not None
    assert variable_response.success is True
    assert variable_response.request is not None
