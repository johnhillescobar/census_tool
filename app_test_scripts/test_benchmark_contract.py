import pytest

from src.domain.benchmark_contract import BenchmarkIntent
from src.services import resolve_benchmark_intent


def test_conflict_requires_clarification():
    result = resolve_benchmark_intent(
        "compare population baseline vs 2019 and peer group counties"
    )
    assert result.status == "clarification_required"
    assert result.reason_code == "BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP"
    assert (
        result.clarification_prompt.template_id
        == "benchmark.conflict_baseline_vs_peer_group.v1"
    )
    assert [o.option_id for o in result.clarification_prompt.options] == [
        "baseline",
        "peer_group",
    ]


def test_missing_metric_requires_clarification():
    result = resolve_benchmark_intent("compare state vs national")
    assert result.status == "clarification_required"
    assert result.reason_code == "BENCHMARK_MISSING_METRIC"
    assert result.clarification_prompt.template_id == "benchmark.missing_metric.v1"

    option_ids = [o.option_id for o in result.clarification_prompt.options]
    # Stable checks: verify key options are present.
    for required in [
        "population",
        "median_income",
        "unemployment",
        "education",
        "cancel",
    ]:
        assert required in option_ids


def test_ambiguous_target_requires_clarification():
    result = resolve_benchmark_intent("compare unemployment with peer group")
    assert result.status == "clarification_required"
    assert result.reason_code == "BENCHMARK_AMBIGUOUS_TARGET"
    assert result.clarification_prompt.template_id == "benchmark.ambiguous_target.v1"
    assert [o.option_id for o in result.clarification_prompt.options] == [
        "subject_geo",
    ]


def test_missing_geo_level_requires_clarification():
    result = resolve_benchmark_intent("compare population")
    assert result.status == "clarification_required"
    assert result.reason_code == "BENCHMARK_MISSING_GEO_LEVEL"
    assert result.clarification_prompt.template_id == "benchmark.missing_geo_level.v1"
    assert [o.option_id for o in result.clarification_prompt.options] == [
        "geo_level",
    ]


def test_resolved_national_benchmark():
    result = resolve_benchmark_intent("compare population against national average")
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "national"
    assert result.benchmark.subject_geo_level == "state"
    assert result.benchmark.subject_geo == ["subject:unknown"]
    assert result.benchmark.benchmark_geo_level == "nation"
    assert result.benchmark.benchmark_geos == ["us:1"]
    assert result.benchmark.metric == "population"
    assert result.benchmark.comparison_op == "difference"
    assert result.benchmark.normalization == "none"


def test_resolved_state_benchmark():
    result = resolve_benchmark_intent("compare population across states")
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "state"
    assert result.benchmark.benchmark_geo_level == "state"
    assert result.benchmark.metric == "population"


def test_resolved_peer_group_benchmark():
    result = resolve_benchmark_intent("compare population for counties")
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "peer_group"
    assert result.benchmark.benchmark_geo_level == "county"
    assert len(result.benchmark.benchmark_geos) >= 2


def test_peer_language_with_explicit_geo_resolves():
    result = resolve_benchmark_intent(
        "compare unemployment for counties with peer group"
    )
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "peer_group"
    assert result.benchmark.benchmark_geo_level == "county"


def test_fallback_ambiguous_target_for_unmapped_input():
    result = resolve_benchmark_intent("population trends")
    assert result.status == "clarification_required"
    assert result.reason_code == "BENCHMARK_AMBIGUOUS_TARGET"
    assert result.clarification_prompt.template_id == "benchmark.ambiguous_target.v1"


# historical_baseline contract validation
def test_historical_baseline_valid_intent():
    intent = BenchmarkIntent(
        benchmark_type="historical_baseline",
        subject_geo_level="county",
        subject_geo=["10001"],
        benchmark_geo_level=None,
        benchmark_geos=[],
        metric="population",
        comparison_op="difference",
        normalization="none",
        baseline_anchor_year=2019,
        baseline_window=1,
        requested_text="compare population vs 2019 baseline",
    )
    assert intent.baseline_anchor_year == 2019
    assert intent.baseline_window == 1


def test_historical_baseline_missing_anchor_rejected():
    with pytest.raises(ValueError, match="historical_baseline requires baseline_anchor_year"):
        BenchmarkIntent(
            benchmark_type="historical_baseline",
            subject_geo_level="county",
            subject_geo=["10001"],
            benchmark_geo_level=None,
            benchmark_geos=[],
            metric="population",
            comparison_op="difference",
            normalization="none",
            requested_text="compare population baseline",
        )


def test_historical_baseline_invalid_window_rejected():
    with pytest.raises(ValueError, match="baseline_window must be >= 1"):
        BenchmarkIntent(
            benchmark_type="historical_baseline",
            subject_geo_level="county",
            subject_geo=["10001"],
            benchmark_geo_level=None,
            benchmark_geos=[],
            metric="population",
            comparison_op="difference",
            normalization="none",
            baseline_anchor_year=2019,
            baseline_window=0,
            requested_text="compare population vs 2019 baseline",
        )


def test_non_baseline_rejects_baseline_fields():
    with pytest.raises(
        ValueError,
        match="baseline_anchor_year and baseline_window are only valid for historical_baseline",
    ):
        BenchmarkIntent(
            benchmark_type="national",
            subject_geo_level="state",
            subject_geo=["subject:unknown"],
            benchmark_geo_level="nation",
            benchmark_geos=["us:1"],
            metric="population",
            comparison_op="difference",
            normalization="none",
            baseline_anchor_year=2019,
            requested_text="compare population against national average",
        )


def test_resolved_historical_baseline_policy():
    result = resolve_benchmark_intent("compare population vs 2019 baseline")
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "historical_baseline"
    assert result.benchmark.baseline_anchor_year == 2019
    assert result.benchmark.benchmark_geos == []


def test_missing_baseline_anchor_requires_clarification():
    result = resolve_benchmark_intent("compare population historical baseline")
    assert result.status == "clarification_required"
    assert result.reason_code == "BENCHMARK_MISSING_BASELINE_ANCHOR"
    assert result.clarification_prompt.template_id == "benchmark.missing_baseline_anchor.v1"


def test_named_states_compare_resolves_without_clarification():
    result = resolve_benchmark_intent("Compare California vs Texas population in 2020")
    assert result.status == "resolved"
    assert isinstance(result.benchmark.benchmark_type, str)


def test_named_states_compare_uses_custom_set():
    result = resolve_benchmark_intent("Compare California vs Texas population in 2020")
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "custom_set"
    assert result.benchmark.benchmark_geo_level == "state"
    assert set(result.benchmark.benchmark_geos) == {"state:06", "state:48"}
    assert set(result.benchmark.subject_geo) == {"state:06", "state:48"}


def test_existing_county_keyword_still_resolves():
    result = resolve_benchmark_intent("Compare population by county in California")
    assert result.status == "resolved"
    assert result.benchmark.benchmark_type == "peer_group"
    assert result.benchmark.benchmark_geo_level == "county"
