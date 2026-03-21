from config import LATEST_AVAILABLE_YEAR
from src.domain.benchmark_contract import BenchmarkIntent
from src.domain.temporal_contract import TemporalIntent
from src.domain.comparison_plan import ComparisonPlan, CensusDataset


def _expand_query_years(temporal_intent: TemporalIntent) -> list[int]:
    if temporal_intent.mode == "point_in_time":
        if temporal_intent.anchor_year is None:
            raise ValueError("Anchor year is required for point in time mode.")

        return [temporal_intent.anchor_year]

    if temporal_intent.mode in {"range", "multi_period_compare"}:
        if temporal_intent.start_year is None or temporal_intent.end_year is None:
            raise ValueError(
                "Start year and end year are required for range and multi period compare modes."
            )

        return list(range(temporal_intent.start_year, temporal_intent.end_year + 1))

    if temporal_intent.mode in {"rolling", "latest_available"}:
        return [LATEST_AVAILABLE_YEAR]

    raise ValueError(f"Unsupported temporal mode: {temporal_intent.mode}")


def _expand_requested_text(
    temporal_intent: TemporalIntent, benchmark_intent: BenchmarkIntent
) -> str:
    if benchmark_intent.requested_text:
        return benchmark_intent.requested_text
    elif temporal_intent.requested_text:
        return temporal_intent.requested_text

    return ""


def resolve_comparison_plan(
    benchmark_intent: BenchmarkIntent,
    temporal_intent: TemporalIntent,
    dataset: CensusDataset = "acs/acs5",
) -> ComparisonPlan:
    """Build the comparison plan from the benchmark intent and temporal intent."""

    query_years = _expand_query_years(temporal_intent)
    requested_text = _expand_requested_text(temporal_intent, benchmark_intent)
    comparison_plan = ComparisonPlan.model_validate(
        {
            "query_years": query_years,
            "dataset": dataset,
            "derived_metrics": [benchmark_intent.comparison_op],
            "join_keys": ["year", "geo_id"],
            "metric": benchmark_intent.metric,
            "subject_geo_level": benchmark_intent.subject_geo_level,
            "subject_geos": benchmark_intent.subject_geo,
            "benchmark_geo_level": benchmark_intent.benchmark_geo_level,
            "benchmark_geos": benchmark_intent.benchmark_geos,
            "comparison_op": benchmark_intent.comparison_op,
            "normalization": benchmark_intent.normalization,
            "missing_year_policy": temporal_intent.missing_year_policy,
            "requested_text": requested_text,
        }
    )
    return comparison_plan
