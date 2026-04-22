from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.temporal_contract import TemporalIntent, TemporalMode
from src.services.comparison_plan_policy import resolve_comparison_plan


def _build_benchmark_intent() -> BenchmarkIntent:
    return BenchmarkIntent(
        benchmark_type="peer_group",
        metric="population",
        subject_geo_level="county",
        subject_geo=["10001", "10002", "10003"],
        benchmark_geo_level="county",
        benchmark_geos=["10001", "10002", "10003"],
        comparison_op="difference",
        normalization="none",
        requested_text="population of california in 2020",
    )


def _build_temporal_intent(
    mode: TemporalMode,
    start_year: int | None,
    end_year: int | None,
    anchor_year: int | None,
) -> TemporalIntent:
    return TemporalIntent(
        mode=mode,
        start_year=start_year,
        end_year=end_year,
        anchor_year=anchor_year,
        requested_text=None,
    )


def _assert_common_plan_fields(plan) -> None:
    assert plan.dataset == "acs/acs5"
    assert plan.metric == "population"
    assert plan.subject_geo_level == "county"
    assert plan.subject_geos == ["10001", "10002", "10003"]
    assert plan.benchmark_geo_level == "county"
    assert plan.benchmark_geos == ["10001", "10002", "10003"]
    assert plan.comparison_op == "difference"
    assert plan.normalization == "none"
    assert plan.missing_year_policy == "skip_with_note"
    assert plan.derived_metrics == ["difference"]
    assert plan.join_keys == ["year", "geo_id"]
    assert plan.requested_text == "population of california in 2020"


def test_point_in_time():
    result = resolve_comparison_plan(
        _build_benchmark_intent(),
        _build_temporal_intent("point_in_time", None, None, 2020),
    )
    assert result.query_years == [2020]
    _assert_common_plan_fields(result)


def test_range():
    result = resolve_comparison_plan(
        _build_benchmark_intent(),
        _build_temporal_intent("range", 2020, 2022, None),
    )
    assert result.query_years == [2020, 2021, 2022]
    _assert_common_plan_fields(result)


def test_latest_available():
    result = resolve_comparison_plan(
        _build_benchmark_intent(),
        _build_temporal_intent("latest_available", None, None, None),
    )
    assert result.query_years == [2023]
    _assert_common_plan_fields(result)


def test_deterministic_rerun_same_input_same_output():
    benchmark_intent = _build_benchmark_intent()
    temporal_intent = _build_temporal_intent("range", 2020, 2022, None)

    first_result = resolve_comparison_plan(benchmark_intent, temporal_intent)
    second_result = resolve_comparison_plan(benchmark_intent, temporal_intent)

    assert first_result.model_dump() == second_result.model_dump()
