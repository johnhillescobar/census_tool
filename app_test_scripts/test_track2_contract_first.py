from typing import Any

import pytest
from pydantic_core import ValidationError

from app import _route_after_benchmark
from src.domain.agent_output_contract import AgentSolveResult
from src.domain.benchmark_contract import BenchmarkIntent, BenchmarkResolved
from src.domain.census_tool_contract import StrictCensusApiResponse, no_strict_census_payload
from src.domain.comparison_metric_contract import ComparisonInputRow
from src.domain.comparison_plan import ComparisonPlan
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.state.types import (
    BenchmarkNotApplicable,
    CensusState,
    FinalResponseState,
    WorkflowArtifactsState,
    WorkflowPlanState,
    _merge_artifacts,
)
from src.tools.geography_validation_tool import GeographyValidationTool
from src.tools.strict_census_api_tool import StrictCensusApiTool
from src.tools.variable_validation_tool import VariableValidationTool
from src.workflows.agent import agent_reasoning_node
from src.workflows.benchmark import benchmark_node
from src.workflows.comparison import comparison_node
from src.workflows.comparison_metrics import comparison_metrics_node
from src.workflows.temporal import temporal_node


def _mini_census_state(
    *,
    messages: list[dict[str, Any]],
    plan: WorkflowPlanState | None = None,
    artifacts: WorkflowArtifactsState | None = None,
) -> CensusState:
    """Construct state with optional fields Pyright expects spelled out."""
    return CensusState(
        messages=messages,
        original_query=None,
        intent=None,
        geo={},
        candidates={},
        plan=plan,
        artifacts=artifacts if artifacts is not None else WorkflowArtifactsState(),
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )


def _build_temporal_resolved() -> TemporalResolved:
    return TemporalResolved(
        time=TemporalIntent(
            mode="point_in_time",
            anchor_year=2023,
            requested_text="population in 2023",
            start_year=None,
            end_year=None,
            rolling_window_years=None,
        )
    )


def _minimal_agent_solve_payload() -> dict:
    return {
        "census_data": no_strict_census_payload().model_dump(mode="python"),
        "data_summary": "summary",
        "reasoning_trace": "trace",
        "answer_text": "answer",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": [],
    }


def _minimal_strict_census_api_response_dict() -> dict:
    return {
        "success": True,
        "request": {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME"],
            "geo_for": {"place": "44000"},
            "geo_in": {"state": "06"},
            "geo_in_chained": [],
        },
        "headers": ["NAME"],
        "records": [{"values": {"NAME": "Los Angeles"}}],
        "row_count": 1,
        "error": None,
        "error_message": None,
    }


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
    state = _mini_census_state(
        messages=[{"content": "Compare county populations"}],
        plan=WorkflowPlanState(
            temporal=_build_temporal_resolved(),
            benchmark=_build_benchmark_resolved(),
            requires_clarification=False,
        ),
    )

    result = comparison_node(state, {})
    merged_plan = WorkflowPlanState.model_validate(result["plan"])

    assert isinstance(merged_plan, WorkflowPlanState)
    assert isinstance(merged_plan.comparison, ComparisonPlan)
    assert merged_plan.comparison is not None
    assert merged_plan.comparison.query_years == [2023]


def test_workflow_canonical_rolling_peer_comparison_is_deterministic():
    user_message = "compare population for counties over the past 3 years"
    initial_state = _mini_census_state(messages=[{"content": user_message}])

    temporal_result = temporal_node(initial_state, {})
    temporal_plan = WorkflowPlanState.model_validate(temporal_result["plan"])

    benchmark_result = benchmark_node(
        _mini_census_state(
            messages=[{"content": user_message}],
            plan=temporal_plan,
        ),
        {},
    )
    benchmark_plan = WorkflowPlanState.model_validate(benchmark_result["plan"])

    first_comparison = comparison_node(
        _mini_census_state(
            messages=[{"content": user_message}],
            plan=benchmark_plan,
        ),
        {},
    )
    second_comparison = comparison_node(
        _mini_census_state(
            messages=[{"content": user_message}],
            plan=benchmark_plan,
        ),
        {},
    )

    first_plan = WorkflowPlanState.model_validate(first_comparison["plan"])
    second_plan = WorkflowPlanState.model_validate(second_comparison["plan"])

    assert isinstance(first_plan, WorkflowPlanState)
    assert isinstance(first_plan.temporal, TemporalResolved)
    assert first_plan.temporal.time.mode == "rolling"
    assert first_plan.temporal.time.rolling_window_years == 3
    assert isinstance(first_plan.benchmark, BenchmarkResolved)
    assert first_plan.benchmark.benchmark.benchmark_type == "peer_group"
    assert isinstance(first_plan.comparison, ComparisonPlan)
    assert first_plan.comparison.query_years == [2021, 2022, 2023]
    assert first_plan.model_dump() == second_plan.model_dump()


def test_comparison_metrics_node_reads_typed_state():
    comparison_result = comparison_node(
        _mini_census_state(
            messages=[{"content": "Compare county populations"}],
            plan=WorkflowPlanState(
                temporal=_build_temporal_resolved(),
                benchmark=_build_benchmark_resolved(),
                requires_clarification=False,
            ),
        ),
        {},
    )
    plan = WorkflowPlanState.model_validate(comparison_result["plan"])

    state = _mini_census_state(
        messages=[{"content": "Compare county populations"}],
        plan=plan,
        artifacts=WorkflowArtifactsState(
            comparison_input_rows=[
                ComparisonInputRow(
                    year=2023,
                    geo_id="10001",
                    metric="population",
                    value=10.0,
                    benchmark_value=8.0,
                )
            ]
        ),
    )

    result = comparison_metrics_node(state, {})
    patched_artifacts = WorkflowArtifactsState.model_validate(result["artifacts"])

    assert isinstance(patched_artifacts, WorkflowArtifactsState)
    assert patched_artifacts.comparison_metrics[0].derived_metric == "difference"
    assert patched_artifacts.comparison_metrics[0].value == 2.0


def test_route_after_benchmark_handles_typed_not_applicable_plan():
    state = _mini_census_state(
        messages=[{"content": "Population in California"}],
        plan=WorkflowPlanState(
            temporal=_build_temporal_resolved(),
            benchmark=BenchmarkNotApplicable(reason="no_comparison_intent"),
            requires_clarification=False,
        ),
    )

    assert _route_after_benchmark(state) == "agent"


def test_merge_artifacts_preserves_census_data_on_data_summary_only_patch() -> None:
    good = StrictCensusApiResponse.model_validate(_minimal_strict_census_api_response_dict())
    existing = WorkflowArtifactsState(
        census_data=good, data_summary="old_sum", reasoning_trace="rt"
    )
    patch = WorkflowArtifactsState(data_summary="new_sum")
    merged = _merge_artifacts(existing, patch)
    assert merged.data_summary == "new_sum"
    assert merged.census_data.success is True
    assert merged.reasoning_trace == "rt"


def test_agent_reasoning_node_returns_typed_final_and_artifacts(monkeypatch):
    class FakeAgent:
        def solve(self, user_query, intent):
            return AgentSolveResult(
                census_data=no_strict_census_payload(),
                data_summary="summary",
                reasoning_trace="trace",
                answer_text="California has a population according to the ACS.",
                charts_needed=[
                    FinalChartSpec(type="bar", title="Population by Location")
                ],
                tables_needed=[
                    FinalTableSpec(
                        format="csv", filename="population", title="Population"
                    )
                ],
                footnotes=["Source note"],
            )

    monkeypatch.setattr("src.workflows.agent.CensusQueryAgent", FakeAgent)

    result = agent_reasoning_node(
        _mini_census_state(messages=[{"content": "Population in California"}]),
        {},
    )
    patched_artifacts = WorkflowArtifactsState.model_validate(result["artifacts"])
    patched_final = FinalResponseState.model_validate(result["final"])

    assert isinstance(patched_artifacts, WorkflowArtifactsState)
    assert isinstance(patched_final, FinalResponseState)
    assert patched_final.charts_needed[0].type == "bar"
    assert patched_final.charts_needed[0].title == "Population by Location"
    assert patched_final.tables_needed[0].filename == "population"


def test_agent_output_rejects_extra_top_level_key():
    with pytest.raises(ValidationError):
        AgentSolveResult.model_validate(
            {**_minimal_agent_solve_payload(), "legacy_bundle": {"k": 1}}
        )


def test_agent_output_rejects_variable_labels_extra_key():
    with pytest.raises(ValidationError):
        AgentSolveResult.model_validate(
            {
                **_minimal_agent_solve_payload(),
                "variable_labels": {"labels": {}, "not_allowed": True},
            }
        )


def test_strict_census_response_rejects_extra_top_level_key():
    bad = {**_minimal_strict_census_api_response_dict(), "shadow_field": 1}
    with pytest.raises(ValidationError):
        StrictCensusApiResponse.model_validate(bad)


def test_strict_census_response_rejects_extra_request_key():
    inner = _minimal_strict_census_api_response_dict()
    inner["request"] = {**inner["request"], "spurious": True}
    with pytest.raises(ValidationError):
        StrictCensusApiResponse.model_validate(inner)


def test_strict_census_response_rejects_extra_record_key():
    inner = _minimal_strict_census_api_response_dict()
    inner["records"] = [
        {**inner["records"][0], "unexpected_trace": "x"},
    ]
    with pytest.raises(ValidationError):
        StrictCensusApiResponse.model_validate(inner)


def test_agent_output_rejects_extra_chart_fields():
    with pytest.raises(ValidationError):
        AgentSolveResult.model_validate(
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
        AgentSolveResult.model_validate(
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


def test_planning_tools_accept_public_langchain_invoke_payloads(monkeypatch):
    geography_tool = GeographyValidationTool()
    variable_tool = VariableValidationTool()
    strict_api_tool = StrictCensusApiTool()

    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_and_fix_geo_params",
        lambda dataset, year, geo_for, geo_in, **kwargs: (
            "us",
            "1",
            [],
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
                    "concept": "Median income",
                    "label": "Median income",
                    "universe": "Households",
                    "dataset": dataset,
                }
                for var in variables
            },
            "alternatives": {},
            "source": {var: "test" for var in variables},
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "src.tools.strict_census_api_tool.build_geo_filters",
        lambda dataset, year, geo_for, geo_in, geo_in_chained: {"for": "us:1"},
    )
    monkeypatch.setattr(
        "src.tools.strict_census_api_tool.fetch_census_data",
        lambda dataset, year, variables, geo: {
            "success": True,
            "data": [
                ["NAME", "S1903_C03_001E"],
                ["United States", "75000"],
            ],
            "url": "https://api.census.gov/data/test",
        },
    )

    geography_response = geography_tool.invoke(
        {
            "dataset": "acs/acs5/subject",
            "year": 2015,
            "geo_for": {"us": "1"},
        }
    )
    variable_response = variable_tool.invoke(
        {
            "action": "validate_variables",
            "dataset": "acs/acs5/subject",
            "year": 2015,
            "variables": ["NAME", "S1903_C03_001E"],
        }
    )
    strict_api_response = strict_api_tool.invoke(
        {
            "year": 2015,
            "dataset": "acs/acs5/subject",
            "variables": ["NAME", "S1903_C03_001E"],
            "geo_for": {"us": "1"},
        }
    )

    assert geography_response.success is True
    assert geography_response.request is not None
    assert geography_response.request.dataset == "acs/acs5/subject"
    assert variable_response.success is True
    assert variable_response.request is not None
    assert variable_response.request.variables == ["NAME", "S1903_C03_001E"]
    assert strict_api_response.success is True
    assert strict_api_response.request is not None
    assert strict_api_response.request.dataset == "acs/acs5/subject"


def test_geography_validation_rejects_prior_observation_as_next_request():
    tool = GeographyValidationTool()
    prior_observation = (
        '{"is_valid":true,"repaired_for":{"us":"1"},"repaired_in":null,'
        '"warnings":[],"errors":[]}'
    )

    response = tool.invoke(prior_observation)

    assert response.success is False
    assert response.request is None
    assert response.error == "INVALID_INPUT_SCHEMA"
    assert "Field required" in response.error_message
    assert "input_value='{" not in response.error_message
