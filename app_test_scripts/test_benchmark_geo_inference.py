import pytest
from pydantic import ValidationError

from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.benchmark_geo_inference import DetectedGeoContext
from src.services.benchmark_geo_inference import (
    build_state_geo_ids,
    extract_geo_candidates,
    infer_geo_context,
    lookup_state_fips,
)
from src.services.benchmark_policy import resolve_benchmark_intent


def test_detected_geo_context_rejects_invalid_fips():
    with pytest.raises(ValidationError):
        DetectedGeoContext(geo_level="state", state_fips=["999"])


def test_detected_geo_context_accepts_valid_state_level():
    ctx = DetectedGeoContext(geo_level="state", state_fips=["06", "48"])
    assert ctx.geo_level == "state"
    assert ctx.state_fips == ["06", "48"]


def test_detected_geo_context_geo_level_is_literal():
    with pytest.raises(ValidationError):
        DetectedGeoContext(geo_level="invalid_level")  # type: ignore[arg-type]


def test_extract_geo_candidates_splits_vs_phrases():
    candidates = extract_geo_candidates("Compare CA vs TX population")
    assert "CA" in candidates or any("ca" in c.lower() for c in candidates)
    assert "TX" in candidates or any("tx" in c.lower() for c in candidates)


def test_lookup_state_fips_by_name_and_abbrev():
    assert lookup_state_fips("California") == "06"
    assert lookup_state_fips("TX") == "48"


def test_infer_geo_context_keyword_priority_unchanged():
    ctx = infer_geo_context("compare population by county in California")
    assert ctx.geo_level == "county"


def test_infer_geo_context_from_named_states():
    ctx = infer_geo_context("Compare California vs Texas population in 2020")
    assert ctx.geo_level == "state"
    assert "06" in ctx.state_fips
    assert "48" in ctx.state_fips


def test_infer_geo_context_returns_none_level_for_vague_compare():
    ctx = infer_geo_context("compare population")
    assert ctx.geo_level is None


def test_build_state_geo_ids_validates_fips():
    assert build_state_geo_ids(["06", "48"]) == ["state:06", "state:48"]
    with pytest.raises(ValidationError):
        build_state_geo_ids(["999"])


def test_custom_set_benchmark_intent_pydantic_round_trip():
    result = resolve_benchmark_intent("Compare California vs Texas population in 2020")
    assert result.status == "resolved"
    round_trip = BenchmarkIntent.model_validate(result.benchmark.model_dump())
    assert round_trip.benchmark_type == "custom_set"
    assert round_trip.benchmark_geo_level == "state"
    assert set(round_trip.benchmark_geos) == {"state:06", "state:48"}


def test_malformed_custom_set_fails_pydantic():
    with pytest.raises(ValidationError):
        BenchmarkIntent(
            benchmark_type="custom_set",
            subject_geo_level="state",
            subject_geo=["state:06"],
            benchmark_geo_level="state",
            benchmark_geos=[],
            metric="population",
            comparison_op="difference",
            normalization="none",
            requested_text="compare",
        )
