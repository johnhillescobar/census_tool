import re
from typing import Literal, cast

from pydantic import ValidationError

from src.domain.benchmark_contract import (
    BenchmarkClarificationRequired,
    BenchmarkIntent,
    BenchmarkResolution,
    BenchmarkResolved,
)
from src.domain.benchmark_geo_inference import DetectedGeoContext
from src.domain.clarification_templates import (
    BenchmarkAmbiguousTargetSlots,
    BenchmarkConflictBaselineVsPeerGroupSlots,
    BenchmarkMissingGeoLevelSlots,
    BenchmarkMissingMetricSlots,
    render_benchmark_clarification,
)
from src.services.benchmark_geo_inference import (
    build_state_geo_ids,
    infer_geo_context,
)

COMPARE_PATTERN = re.compile(r"\b(compare|vs|versus|against)\b", re.IGNORECASE)

PEER_GROUP_PATTERN = re.compile(
    r"\b(peer group|peer|similar counties|similar states)\b", re.IGNORECASE
)
BASELINE_PATTERN = re.compile(
    r"\b(baseline|vs\s+\d{4}|compared to \d{4}|historical)\b", re.IGNORECASE
)


# Metric hints; expand later
METRIC_HINTS = {
    "population": ["population", "people", "residents", "inhabitants"],
    "median_income": ["median income", "income", "household income", "family income"],
    "unemployment": ["unemployment", "unemployed", "jobless"],
    "education": ["education", "degree", "college", "high school", "graduate"],
    "hispanic": ["hispanic", "latino", "latina", "hispanic or latino"],
    "race": ["race", "racial", "white", "black", "asian", "native"],
}


def _detect_metric(text: str) -> str | None:
    """Detect the metric from the text."""
    text_1 = text.lower()
    for metric, hints in METRIC_HINTS.items():
        if any(hint in text_1 for hint in hints):
            return metric
    return None


def _build_custom_set_state_benchmark(
    ctx: DetectedGeoContext,
    metric: str,
    text: str,
) -> BenchmarkIntent:
    geo_ids = build_state_geo_ids(ctx.state_fips)
    return BenchmarkIntent(
        benchmark_type="custom_set",
        subject_geo_level="state",
        subject_geo=geo_ids,
        benchmark_geo_level="state",
        benchmark_geos=geo_ids,
        metric=metric,
        comparison_op="difference",
        normalization="none",
        requested_text=text,
    )


def _ambiguous_target_clarification(text: str) -> BenchmarkClarificationRequired:
    clarification = render_benchmark_clarification(
        BenchmarkAmbiguousTargetSlots(
            reason_code="BENCHMARK_AMBIGUOUS_TARGET",
            subject_text=text,
        )
    )
    return BenchmarkClarificationRequired(
        status="clarification_required",
        reason_code="BENCHMARK_AMBIGUOUS_TARGET",
        clarification_prompt=clarification,
    )


def resolve_benchmark_intent(user_text: str) -> BenchmarkResolution:
    """Resolve the benchmark intent."""

    text = user_text or ""
    text_1 = text.lower()

    has_compare = bool(COMPARE_PATTERN.search(text_1))
    has_peer_language = bool(PEER_GROUP_PATTERN.search(text_1))
    metric = _detect_metric(text_1)
    geo_ctx = infer_geo_context(text)
    geo_level = geo_ctx.geo_level

    # Conflict clarification: baseline and peer group both requested
    if BASELINE_PATTERN.search(text_1) and PEER_GROUP_PATTERN.search(text_1):
        clarification = render_benchmark_clarification(
            BenchmarkConflictBaselineVsPeerGroupSlots(
                reason_code="BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP",
                subject_text=text,
            )
        )
        return BenchmarkClarificationRequired(
            status="clarification_required",
            reason_code="BENCHMARK_CONFLICT_BASELINE_VS_PEER_GROUP",
            clarification_prompt=clarification,
        )

    # Clarification: missing metric
    if metric is None:
        clarification = render_benchmark_clarification(
            BenchmarkMissingMetricSlots(
                reason_code="BENCHMARK_MISSING_METRIC",
                subject_text=text,
                metric="metric",
            )
        )
        return BenchmarkClarificationRequired(
            status="clarification_required",
            reason_code="BENCHMARK_MISSING_METRIC",
            clarification_prompt=clarification,
        )

    # Clarification: compare language without explicit geography
    if has_compare and geo_level is None:
        if has_peer_language:
            clarification = render_benchmark_clarification(
                BenchmarkAmbiguousTargetSlots(
                    reason_code="BENCHMARK_AMBIGUOUS_TARGET",
                    subject_text=text,
                )
            )
            return BenchmarkClarificationRequired(
                status="clarification_required",
                reason_code="BENCHMARK_AMBIGUOUS_TARGET",
                clarification_prompt=clarification,
            )

        clarification = render_benchmark_clarification(
            BenchmarkMissingGeoLevelSlots(
                reason_code="BENCHMARK_MISSING_GEO_LEVEL",
                subject_text=text,
                geo_level="state",
            )
        )
        return BenchmarkClarificationRequired(
            status="clarification_required",
            reason_code="BENCHMARK_MISSING_GEO_LEVEL",
            clarification_prompt=clarification,
        )

    # Multi-state named comparison -> custom_set at state level
    if has_compare and len(geo_ctx.state_fips) >= 2 and geo_level == "state":
        try:
            benchmark = _build_custom_set_state_benchmark(geo_ctx, metric, text)
            return BenchmarkResolved(status="resolved", benchmark=benchmark)
        except ValidationError:
            return _ambiguous_target_clarification(text)

    # Resolved path starts here (nation/state/peer_group...)
    if geo_level == "nation":
        benchmark = BenchmarkIntent(
            benchmark_type="national",
            subject_geo_level="state",
            subject_geo=["subject:unknown"],
            benchmark_geo_level="nation",
            benchmark_geos=["us:1"],
            metric=metric,
            comparison_op="difference",
            normalization="none",
            requested_text=text,
        )
        return BenchmarkResolved(status="resolved", benchmark=benchmark)

    if geo_level == "state":
        benchmark = BenchmarkIntent(
            benchmark_type="state",
            subject_geo_level="county",
            subject_geo=["subject:unknown"],
            benchmark_geo_level="state",
            benchmark_geos=["state:unknown"],
            metric=metric,
            comparison_op="difference",
            normalization="none",
            requested_text=text,
        )
        return BenchmarkResolved(status="resolved", benchmark=benchmark)

    if geo_level in {"county", "place", "cbsa", "metro_division"}:
        peer_geo_level = cast(
            Literal["county", "place", "cbsa", "metro_division"], geo_level
        )
        benchmark = BenchmarkIntent(
            benchmark_type="peer_group",
            subject_geo_level=peer_geo_level,
            subject_geo=["subject:unknown"],
            benchmark_geo_level=peer_geo_level,
            benchmark_geos=["peer:1", "peer:2"],
            metric=metric,
            comparison_op="difference",
            normalization="none",
            requested_text=text,
        )
        return BenchmarkResolved(status="resolved", benchmark=benchmark)

    return _ambiguous_target_clarification(text)
