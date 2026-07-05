import pytest

from src.domain.comparison_artifacts import (
    ComparisonCensusObservation,
    ComparisonInputRowBuildRequest,
)
from src.domain.comparison_plan import ComparisonPlan
from src.services.comparison_input_builder import (
    build_comparison_input_rows,
    extract_observations_from_census_data,
)


def _build_peer_group_plan() -> ComparisonPlan:
    return ComparisonPlan(
        query_years=[2020],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["10001", "10002", "10003"],
        benchmark_geo_level="county",
        benchmark_geos=["10001", "10002", "10003"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare counties",
    )


def _build_national_plan() -> ComparisonPlan:
    return ComparisonPlan(
        query_years=[2020],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="state",
        subject_geos=["06", "48"],
        benchmark_geo_level="nation",
        benchmark_geos=["us:1"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare states to national",
    )


def test_extract_observations_from_census_data_happy_path():
    plan = _build_peer_group_plan()
    census_data = {
        "success": True,
        "url": "https://api.census.gov/data/2020/acs/acs5",
        "data": [
            ["geo_id", "year", "B01003_001E"],
            ["10001", "2020", "100"],
            ["10002", "2020", "80"],
            ["10003", "2020", "60"],
        ],
    }

    observations = extract_observations_from_census_data(census_data, plan)

    assert len(observations) == 3
    assert observations[0].geo_id == "10001"
    assert observations[0].value == 100.0
    assert observations[0].year == 2020


def test_build_comparison_input_rows_peer_group_mean_pairing():
    plan = _build_peer_group_plan()
    observations = [
        ComparisonCensusObservation(
            year=2020, geo_id="10001", metric="population", value=100.0
        ),
        ComparisonCensusObservation(
            year=2020, geo_id="10002", metric="population", value=80.0
        ),
        ComparisonCensusObservation(
            year=2020, geo_id="10003", metric="population", value=60.0
        ),
    ]

    rows = build_comparison_input_rows(
        ComparisonInputRowBuildRequest(plan=plan, observations=observations)
    )

    assert len(rows) == 3
    by_geo = {row.geo_id: row for row in rows}
    assert by_geo["10001"].benchmark_value == 70.0
    assert by_geo["10002"].benchmark_value == 80.0
    assert by_geo["10003"].benchmark_value == 90.0


def test_build_comparison_input_rows_national_benchmark_pairing():
    plan = _build_national_plan()
    observations = [
        ComparisonCensusObservation(
            year=2020, geo_id="06", metric="population", value=39500000.0
        ),
        ComparisonCensusObservation(
            year=2020, geo_id="48", metric="population", value=29100000.0
        ),
        ComparisonCensusObservation(
            year=2020, geo_id="us:1", metric="population", value=331000000.0
        ),
    ]

    rows = build_comparison_input_rows(
        ComparisonInputRowBuildRequest(plan=plan, observations=observations)
    )

    assert len(rows) == 2
    for row in rows:
        assert row.benchmark_value == 331000000.0


def test_extract_observations_fail_closed_on_empty_data():
    plan = _build_peer_group_plan()
    with pytest.raises(ValueError, match="must include headers and at least one row"):
        extract_observations_from_census_data({"success": True, "data": [["geo_id"]]}, plan)


def test_build_comparison_input_rows_fail_closed_missing_subject_observation():
    plan = ComparisonPlan(
        query_years=[2020],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["10002"],
        benchmark_geo_level="county",
        benchmark_geos=["10002"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare counties",
    )
    observations = [
        ComparisonCensusObservation(
            year=2020, geo_id="10001", metric="population", value=100.0
        )
    ]

    with pytest.raises(ValueError, match="missing subject observation"):
        build_comparison_input_rows(
            ComparisonInputRowBuildRequest(plan=plan, observations=observations)
        )


def test_build_comparison_input_rows_fail_closed_missing_national_benchmark():
    plan = _build_national_plan()
    observations = [
        ComparisonCensusObservation(
            year=2020, geo_id="06", metric="population", value=39500000.0
        )
    ]

    with pytest.raises(ValueError, match="missing benchmark observation"):
        build_comparison_input_rows(
            ComparisonInputRowBuildRequest(plan=plan, observations=observations)
        )


def test_build_comparison_input_rows_deterministic_rerun():
    plan = _build_peer_group_plan()
    observations = [
        ComparisonCensusObservation(
            year=2020, geo_id="10003", metric="population", value=60.0
        ),
        ComparisonCensusObservation(
            year=2020, geo_id="10001", metric="population", value=100.0
        ),
        ComparisonCensusObservation(
            year=2020, geo_id="10002", metric="population", value=80.0
        ),
    ]
    request = ComparisonInputRowBuildRequest(plan=plan, observations=observations)

    first = build_comparison_input_rows(request)
    second = build_comparison_input_rows(request)

    assert [row.model_dump() for row in first] == [row.model_dump() for row in second]
