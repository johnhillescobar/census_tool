import pytest
from pydantic import ValidationError

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.comparison_plan import ComparisonPlan
from src.domain.temporal_contract import TemporalIntent
from src.services.agent_plan_context import (
    build_agent_plan_context,
    format_plan_directives,
)
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
        requested_text="compare population counties",
    )


def _build_temporal_intent() -> TemporalIntent:
    return TemporalIntent(
        mode="range",
        start_year=2020,
        end_year=2022,
        anchor_year=None,
        requested_text="compare population counties",
    )


def _build_comparison_plan() -> ComparisonPlan:
    return resolve_comparison_plan(_build_benchmark_intent(), _build_temporal_intent())


def _build_full_state_plan() -> dict:
    temporal = _build_temporal_intent()
    benchmark = _build_benchmark_intent()
    comparison = _build_comparison_plan()
    return {
        "temporal": {
            "status": "resolved",
            "time": temporal.model_dump(),
        },
        "benchmark": {
            "status": "resolved",
            "benchmark": benchmark.model_dump(),
        },
        "comparison": comparison.model_dump(),
        "requires_clarification": False,
    }


def test_valid_temporal_only_context():
    temporal = TemporalIntent(
        mode="latest_available",
        start_year=None,
        end_year=None,
        anchor_year=None,
        requested_text="population of california",
    )
    context = AgentPlanContext(
        temporal=temporal,
        benchmark=None,
        comparison=None,
        has_comparison_plan=False,
    )
    assert context.temporal.mode == "latest_available"
    assert context.has_comparison_plan is False


def test_valid_full_comparison_context():
    context = AgentPlanContext(
        temporal=_build_temporal_intent(),
        benchmark=_build_benchmark_intent(),
        comparison=_build_comparison_plan(),
        has_comparison_plan=True,
    )
    assert context.comparison is not None
    assert context.comparison.query_years == [2020, 2021, 2022]


def test_comparison_flag_requires_comparison_plan():
    with pytest.raises(ValidationError, match="comparison must be provided"):
        AgentPlanContext(
            temporal=_build_temporal_intent(),
            benchmark=_build_benchmark_intent(),
            comparison=None,
            has_comparison_plan=True,
        )


def test_build_from_resolved_state_plan_dict():
    context = build_agent_plan_context(_build_full_state_plan())
    assert context is not None
    assert context.has_comparison_plan is True
    assert context.comparison.query_years == [2020, 2021, 2022]


def test_build_temporal_only_not_applicable():
    temporal = TemporalIntent(
        mode="latest_available",
        start_year=None,
        end_year=None,
        anchor_year=None,
        requested_text="population of california",
    )
    plan = {
        "temporal": {"status": "resolved", "time": temporal.model_dump()},
        "benchmark": {"status": "not_applicable", "reason": "no_comparison_intent"},
        "requires_clarification": False,
    }
    context = build_agent_plan_context(plan)
    assert context is not None
    assert context.has_comparison_plan is False
    assert context.temporal.mode == "latest_available"
    assert context.benchmark is None


def test_build_invalid_plan_returns_none():
    assert build_agent_plan_context({"requires_clarification": True}) is None
    assert build_agent_plan_context({"temporal": {"status": "broken"}}) is None
    assert build_agent_plan_context(None) is None


def test_format_plan_directives_deterministic():
    context = build_agent_plan_context(_build_full_state_plan())
    first = format_plan_directives(context)
    second = format_plan_directives(context)
    assert first == second
    assert "Query years: [2020, 2021, 2022]" in first
    assert "Dataset: acs/acs5" in first


def test_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AgentPlanContext(
            temporal=_build_temporal_intent(),
            benchmark=None,
            comparison=None,
            has_comparison_plan=False,
            unexpected_field=True,
        )
