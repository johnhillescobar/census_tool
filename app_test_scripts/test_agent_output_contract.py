import pytest
from pydantic import ValidationError

from src.domain.agent_output_contract import (
    AgentPlanOutput,
    agent_output_to_legacy_dict,
    validate_comparison_rows_for_plan,
)
from src.domain.census_tool_contract import (
    StrictCensusApiRecord,
    StrictCensusApiRequest,
    StrictCensusApiResponse,
)
from src.domain.comparison_input_contract import ComparisonInputRow
from src.domain.comparison_plan import ComparisonPlan


def _build_plan() -> ComparisonPlan:
    return ComparisonPlan(
        query_years=[2020, 2021],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["10001", "10002"],
        benchmark_geo_level="county",
        benchmark_geos=["10001", "10002"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare counties",
    )


def _build_output_payload(rows: list[dict] | None = None) -> dict:
    return {
        "census_data": {"success": True, "data": [["NAME"], ["County A"]]},
        "data_summary": "summary",
        "reasoning_trace": "trace",
        "answer_text": "answer",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": ["Source: Census"],
        "comparison_input_rows": rows or [],
    }


def test_valid_comparison_input_rows():
    rows = [
        ComparisonInputRow(
            year=2020,
            geo_id="10001",
            metric="population",
            value=10.0,
            benchmark_value=8.0,
        )
    ]
    output = AgentPlanOutput(**_build_output_payload([row.model_dump() for row in rows]))
    validated = validate_comparison_rows_for_plan(rows, _build_plan())
    assert len(output.comparison_input_rows) == 1
    assert len(validated) == 1


def test_agent_plan_output_preserves_strict_census_response_until_legacy_boundary():
    strict_response = StrictCensusApiResponse(
        success=True,
        request=StrictCensusApiRequest(
            year=2023,
            dataset="acs/acs5",
            variables=["NAME", "B01003_001E"],
            geo_for={"state": "06"},
        ),
        headers=["NAME", "B01003_001E"],
        records=[StrictCensusApiRecord(values={"NAME": "California", "B01003_001E": "39538223"})],
        row_count=1,
        error=None,
        error_message=None,
    )
    output = AgentPlanOutput(
        census_data=strict_response,
        data_summary="summary",
        reasoning_trace="trace",
        answer_text="answer",
        charts_needed=[],
        tables_needed=[],
        footnotes=[],
        comparison_input_rows=[],
    )

    assert isinstance(output.census_data, StrictCensusApiResponse)

    legacy = agent_output_to_legacy_dict(output)
    assert legacy["census_data"] == {
        "success": True,
        "data": [["NAME", "B01003_001E"], ["California", "39538223"]],
        "variables": {"NAME": "NAME", "B01003_001E": "B01003_001E"},
        "url": "https://api.census.gov/data/2023/acs/acs5",
    }


def test_rejects_placeholder_geo_ids():
    with pytest.raises(ValidationError, match="unresolved placeholder geo_id"):
        AgentPlanOutput(
            **_build_output_payload(
                [
                    {
                        "year": 2020,
                        "geo_id": "subject:unknown",
                        "metric": "population",
                        "value": 10.0,
                        "benchmark_value": 8.0,
                    }
                ]
            )
        )


def test_rejects_year_outside_plan():
    rows = [
        ComparisonInputRow(
            year=2019,
            geo_id="10001",
            metric="population",
            value=10.0,
            benchmark_value=8.0,
        )
    ]
    with pytest.raises(ValueError, match="row year is outside plan.query_years"):
        validate_comparison_rows_for_plan(rows, _build_plan())


def _build_placeholder_plan() -> ComparisonPlan:
    return ComparisonPlan(
        query_years=[2020],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["subject:unknown"],
        benchmark_geo_level="county",
        benchmark_geos=["peer:1", "peer:2"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare counties",
    )


def test_accepts_resolved_geos_when_plan_uses_placeholders():
    rows = [
        ComparisonInputRow(
            year=2020,
            geo_id="06001",
            metric="population",
            value=100.0,
            benchmark_value=90.0,
        ),
        ComparisonInputRow(
            year=2020,
            geo_id="06037",
            metric="population",
            value=200.0,
            benchmark_value=150.0,
        ),
    ]

    validated = validate_comparison_rows_for_plan(rows, _build_placeholder_plan())

    assert len(validated) == 2
