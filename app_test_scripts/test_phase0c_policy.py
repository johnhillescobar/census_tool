from src.domain.agent_plan_context import AgentPlanContext
from src.domain.execution_spec import build_execution_spec
from src.domain.geography_contract import GeographyIntent, GeographyResolved
from src.domain.temporal_contract import TemporalIntent
from src.services.agent_plan_context import build_agent_plan_context
from src.services.plan_result_validator import validate_agent_result_against_plan
from src.state.workflow_plan import TemporalResolved, WorkflowPlan
from src.workflows.output import is_census_data_renderable


def _grounded_us_context() -> AgentPlanContext:
    return AgentPlanContext(
        geography=GeographyIntent(
            level="nation",
            geo_for={"us": "1"},
            geo_in={},
            display_name="United States",
            source="chroma",
        ),
        temporal=TemporalIntent(
            mode="range",
            start_year=2015,
            end_year=2020,
            anchor_year=None,
            missing_year_policy="skip_with_note",
            requested_text="Show me median income trends from 2015 to 2020",
        ),
        benchmark=None,
        comparison=None,
        has_comparison_plan=False,
    )


def test_execution_spec_requires_six_years_for_2015_2020():
    spec = build_execution_spec(_grounded_us_context())
    assert spec is not None
    assert spec.query_years == [2015, 2016, 2017, 2018, 2019, 2020]
    assert spec.requires_time_series is True


def test_plan_result_validator_strips_charts_on_failed_agent_output():
    result = validate_agent_result_against_plan(
        {
            "census_data": {"success": False, "data": []},
            "answer_text": "Need more detail",
            "charts_needed": [{"type": "line", "title": "Trend"}],
            "tables_needed": [{"type": "table", "title": "Data"}],
        },
        _grounded_us_context(),
    )
    assert result["charts_needed"] == []
    assert result["tables_needed"] == []


def test_plan_result_validator_rejects_empty_success_series():
    result = validate_agent_result_against_plan(
        {
            "census_data": {"success": True, "data": []},
            "answer_text": "Here is the trend",
            "charts_needed": [{"type": "line", "title": "Trend"}],
            "tables_needed": [],
        },
        _grounded_us_context(),
    )
    assert result["census_data"]["success"] is False
    assert result["charts_needed"] == []


def test_renderability_guard_blocks_failed_payload():
    assert is_census_data_renderable({"success": False, "data": []}) is False


def test_build_agent_plan_context_from_median_income_plan():
    temporal = TemporalIntent(
        mode="range",
        start_year=2015,
        end_year=2020,
        anchor_year=None,
        missing_year_policy="skip_with_note",
        requested_text="Show me median income trends from 2015 to 2020",
    )
    plan = WorkflowPlan(
        geography=GeographyResolved(
            geography=GeographyIntent(
                level="nation",
                geo_for={"us": "1"},
                geo_in={},
                display_name="United States",
                source="chroma",
            )
        ),
        temporal=TemporalResolved(time=temporal),
        requires_clarification=False,
    )
    context = build_agent_plan_context(plan)
    assert context is not None
    assert context.geography is not None
    assert context.geography.geo_for == {"us": "1"}
    spec = build_execution_spec(context)
    assert spec is not None
    assert len(spec.query_years) == 6
