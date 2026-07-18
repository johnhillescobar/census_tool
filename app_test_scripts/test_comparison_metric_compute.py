import pytest

from src.domain.comparison_plan import ComparisonPlan, DerivedMetric
from src.services.comparison_metric_compute import (
    ComparisonInputRow,
    ComparisonMetricComputeRequest,
    compute_comparison_metrics,
)


def _build_plan(derived_metrics: list[DerivedMetric]) -> ComparisonPlan:
    return ComparisonPlan(
        query_years=[2020, 2021],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["10001", "10002", "10003"],
        benchmark_geo_level="county",
        benchmark_geos=["10001", "10002", "10003"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=derived_metrics,
        join_keys=["year", "geo_id"],
        requested_text="compare population for counties",
    )


def _build_rows_two_years() -> list[ComparisonInputRow]:
    return [
        ComparisonInputRow(
            year=2020,
            geo_id="10001",
            metric="population",
            value=100.0,
            benchmark_value=90.0,
        ),
        ComparisonInputRow(
            year=2020,
            geo_id="10002",
            metric="population",
            value=80.0,
            benchmark_value=90.0,
        ),
        ComparisonInputRow(
            year=2020,
            geo_id="10003",
            metric="population",
            value=80.0,
            benchmark_value=80.0,
        ),
        ComparisonInputRow(
            year=2021,
            geo_id="10001",
            metric="population",
            value=120.0,
            benchmark_value=95.0,
        ),
        ComparisonInputRow(
            year=2021,
            geo_id="10002",
            metric="population",
            value=100.0,
            benchmark_value=95.0,
        ),
        ComparisonInputRow(
            year=2021,
            geo_id="10003",
            metric="population",
            value=100.0,
            benchmark_value=100.0,
        ),
    ]


def _row_by_key(results, year: int, geo_id: str, derived_metric: str):
    for row in results:
        if (
            row.year == year
            and row.geo_id == geo_id
            and row.derived_metric == derived_metric
        ):
            return row
    raise AssertionError(f"missing row for ({year}, {geo_id}, {derived_metric})")


def test_compute_all_metrics_happy_path_and_deterministic_order():
    request = ComparisonMetricComputeRequest(
        plan=_build_plan(
            [
                "difference",
                "pct_difference",
                "rank",
                "percentile",
                "trend_gap",
            ]
        ),
        rows=_build_rows_two_years(),
    )

    results = compute_comparison_metrics(request)

    # 6 input rows * 5 derived metrics
    assert len(results) == 30

    # deterministic output ordering
    ordered = sorted(
        results, key=lambda r: (r.year, r.geo_id, r.metric, r.derived_metric)
    )
    assert [r.model_dump() for r in results] == [r.model_dump() for r in ordered]

    # difference and pct_difference
    row_diff = _row_by_key(results, 2020, "10001", "difference")
    assert row_diff.success is True
    assert row_diff.value == 10.0

    row_pct = _row_by_key(results, 2020, "10001", "pct_difference")
    assert row_pct.success is True
    assert row_pct.value == pytest.approx(11.1111111111, rel=1e-6)

    # rank dense with ties in each year:
    # 2020 values: 100, 80, 80 -> ranks 1,2,2
    assert _row_by_key(results, 2020, "10001", "rank").value == 1
    assert _row_by_key(results, 2020, "10002", "rank").value == 2
    assert _row_by_key(results, 2020, "10003", "rank").value == 2

    # percentile in 2020: 100 => 100, 80 => 66.666...
    assert _row_by_key(results, 2020, "10001", "percentile").value == pytest.approx(
        100.0, rel=1e-9
    )
    assert _row_by_key(results, 2020, "10002", "percentile").value == pytest.approx(
        66.6666666667, rel=1e-6
    )
    assert _row_by_key(results, 2020, "10003", "percentile").value == pytest.approx(
        66.6666666667, rel=1e-6
    )

    # trend_gap per geo/metric: (last_gap - first_gap)
    # geo 10001 gap: (120-95) - (100-90) = 25 - 10 = 15
    tg_2020 = _row_by_key(results, 2020, "10001", "trend_gap")
    tg_2021 = _row_by_key(results, 2021, "10001", "trend_gap")
    assert tg_2020.success is True
    assert tg_2021.success is True
    assert tg_2020.value == 15.0
    assert tg_2021.value == 15.0
    assert "first and last available year" in (tg_2020.note or "")


def test_pct_difference_division_by_zero_returns_error():
    plan = _build_plan(["pct_difference"])
    rows = [
        ComparisonInputRow(
            year=2020,
            geo_id="10001",
            metric="population",
            value=10.0,
            benchmark_value=0.0,
        )
    ]
    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    results = compute_comparison_metrics(request)

    assert len(results) == 1
    row = results[0]
    assert row.success is False
    assert row.error == "DIVISION_BY_ZERO"
    assert row.value is None


def test_trend_gap_insufficient_timepoints_fails_closed():
    plan = _build_plan(["trend_gap"])
    rows = [
        ComparisonInputRow(
            year=2020,
            geo_id="10001",
            metric="population",
            value=10.0,
            benchmark_value=8.0,
        )
    ]
    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    results = compute_comparison_metrics(request)

    assert len(results) == 1
    row = results[0]
    assert row.success is False
    assert row.error == "INSUFFICIENT_TIMEPOINTS"
    assert row.value is None


def test_join_keys_contract_must_match_metric_compute_boundary():
    plan = _build_plan(["difference"]).model_copy(update={"join_keys": ["geo_id"]})
    rows = _build_rows_two_years()

    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    with pytest.raises(
        ValueError,
        match="join_keys must be exactly \\['year', 'geo_id'\\] for metric compute",
    ):
        compute_comparison_metrics(request)


def test_row_metric_must_match_plan_metric():
    plan = _build_plan(["difference"])
    rows = _build_rows_two_years()
    rows[0] = rows[0].model_copy(update={"metric": "median_income"})

    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    with pytest.raises(ValueError, match="row metric does not match plan.metric"):
        compute_comparison_metrics(request)


def test_row_year_must_be_within_plan_query_years():
    plan = _build_plan(["difference"])
    rows = _build_rows_two_years()
    rows[0] = rows[0].model_copy(update={"year": 2019})

    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    with pytest.raises(ValueError, match="row year is outside plan.query_years"):
        compute_comparison_metrics(request)


def test_row_geo_must_be_within_plan_subject_geos():
    plan = _build_plan(["difference"])
    rows = _build_rows_two_years()
    rows[0] = rows[0].model_copy(update={"geo_id": "99999"})

    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    with pytest.raises(ValueError, match="row geo_id is outside plan.subject_geos"):
        compute_comparison_metrics(request)


def test_accepts_resolved_geos_when_plan_uses_placeholders():
    plan = ComparisonPlan(
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
    rows = [
        ComparisonInputRow(
            year=2020,
            geo_id="06001",
            metric="population",
            value=100.0,
            benchmark_value=90.0,
        )
    ]
    request = ComparisonMetricComputeRequest(plan=plan, rows=rows)

    metrics = compute_comparison_metrics(request)

    assert len(metrics) == 1
    assert metrics[0].geo_id == "06001"


