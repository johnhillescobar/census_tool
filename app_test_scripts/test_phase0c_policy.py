from src.domain.agent_plan_context import AgentPlanContext
from src.domain.execution_spec import build_execution_spec
from src.domain.geography_contract import GeographyIntent
from src.domain.temporal_contract import TemporalIntent
from src.services.agent_plan_context import build_agent_plan_context
from src.services.geography_policy import resolve_geography_intent
from src.services.plan_result_validator import validate_agent_result_against_plan
from src.state.workflow_plan import WorkflowPlan, TemporalResolved
from src.domain.geography_contract import GeographyResolved
from src.workflows.output import is_census_data_renderable


def _us_default_context() -> AgentPlanContext:
    return AgentPlanContext(
        geography=GeographyIntent(
            level="nation",
            geo_for={"us": "1"},
            geo_in={},
            display_name="United States",
            source="missing_geo_default",
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


def test_missing_geography_defaults_to_us_national():
    resolution = resolve_geography_intent(
        "Show me median income trends from 2015 to 2020"
    )
    assert resolution.status == "resolved"
    assert resolution.geography.geo_for == {"us": "1"}
    assert resolution.geography.source == "missing_geo_default"


def test_explicit_nyc_does_not_use_us_fallback():
    resolution = resolve_geography_intent("population of nyc")
    assert resolution.status == "resolved"
    assert resolution.geography.geo_for.get("place") == "51000"
    assert resolution.geography.source == "explicit"


def test_execution_spec_requires_six_years_for_2015_2020():
    spec = build_execution_spec(_us_default_context())
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
        _us_default_context(),
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
        _us_default_context(),
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
                source="missing_geo_default",
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
