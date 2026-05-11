import pytest

from src.domain.temporal_contract import TemporalIntent
from src.services.temporal_policy import resolve_temporal_intent


def test_point_in_time_is_resolved():
    result = resolve_temporal_intent("population in 2023")
    assert result.status == "resolved"
    assert result.time.mode == "point_in_time"
    assert result.time.anchor_year == 2023


def test_conflict_requires_clarification():
    result = resolve_temporal_intent("compare 2019 vs 2023 over the last 5 years")
    assert result.status == "clarification_required"
    assert result.reason_code == "TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING"
    assert result.clarification_prompt.template_id == "temporal.explicit_vs_rolling.v1"
    assert [o.option_id for o in result.clarification_prompt.options] == [
        "explicit_compare",
        "rolling_trend",
        "cancel",
    ]


def test_no_temporal_phrase_defaults_latest_available():
    result = resolve_temporal_intent("population of california")
    assert result.status == "resolved"
    assert result.time.mode == "latest_available"


def test_range_is_normalized():
    result = resolve_temporal_intent("population from 2023 to 2019")
    assert result.status == "resolved"
    assert result.time.mode == "range"
    assert result.time.start_year == 2019
    assert result.time.end_year == 2023


def test_rolling_window_is_typed():
    result = resolve_temporal_intent("population over the past 4 years")
    assert result.status == "resolved"
    assert result.time.mode == "rolling"
    assert result.time.rolling_window_years == 4
    assert result.time.start_year is None
    assert result.time.end_year is None
    assert result.time.anchor_year is None


def test_rolling_window_requires_window_size():
    with pytest.raises(ValueError, match="rolling_window_years is required"):
        TemporalIntent(mode="rolling")


def test_non_rolling_rejects_window_size():
    with pytest.raises(ValueError, match="rolling_window_years is only allowed"):
        TemporalIntent(
            mode="point_in_time",
            anchor_year=2023,
            rolling_window_years=3,
        )
