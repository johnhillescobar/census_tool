from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field
from src.domain.comparison_plan import ComparisonPlan, DerivedMetric

SUPPORTED_DERIVED_METRICS = {
    "difference",
    "pct_difference",
    "rank",
    "percentile",
    "trend_gap",
}


class ComparisonInputRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    geo_id: str
    metric: str
    value: float
    benchmark_value: float


class ComparisonMetricComputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ComparisonPlan
    rows: list[ComparisonInputRow]


class ComparisonMetricRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., description="The year of the metric.")
    geo_id: str = Field(..., description="The geo_id of the metric.")
    metric: str = Field(..., description="The metric of the metric.")
    derived_metric: DerivedMetric = Field(
        ..., description="The derived metric of the metric."
    )
    value: float | None = Field(default=None, description="The value of the metric.")
    subject_value: float | None = Field(
        default=None, description="The subject value of the metric."
    )
    benchmark_value: float | None = Field(
        default=None, description="The benchmark value of the metric."
    )
    note: str | None = Field(None, description="The note of the metric.")
    error: str | None = Field(None, description="The error of the metric.")
    success: bool = Field(
        default=True, description="Whether the metric computation was successful."
    )


def _sorted_rows(rows: list[ComparisonInputRow]) -> list[ComparisonInputRow]:
    """Sort the rows by the join keys."""
    return sorted(rows, key=lambda x: (x.year, x.geo_id, x.metric))


def _compute_difference(subject_value: float, benchmark_value: float) -> float:
    return subject_value - benchmark_value


def _compute_pct_difference(
    subject_value: float, benchmark_value: float
) -> float | None:
    if benchmark_value == 0:
        return None
    return ((subject_value - benchmark_value) / benchmark_value) * 100.0


def _build_rank_map(
    rows: list[ComparisonInputRow],
    *,
    dataset: str | None,
    geo_level: str | None,
) -> dict[tuple[int, str, str], int]:
    if not dataset or not geo_level:
        return {}
    by_group: dict[tuple[int, str, str, str], list[ComparisonInputRow]] = defaultdict(
        list
    )
    for r in rows:
        by_group[(r.year, r.metric, dataset, geo_level)].append(r)
    output: dict[tuple[int, str, str], int] = {}
    for _, group_rows in by_group.items():
        ordered = sorted(
            group_rows, key=lambda x: (-x.value, x.geo_id)
        )  # deterministic
        current_rank = 0
        prev_value: float | None = None
        for row in ordered:
            if prev_value is None or row.value != prev_value:
                current_rank += 1
                prev_value = row.value
            output[(row.year, row.geo_id, row.metric)] = current_rank
    return output


def _build_percentile_map(
    rows: list[ComparisonInputRow],
) -> dict[tuple[int, str, str], float]:
    """
    Percentile is computed within (year, metric) peer groups.
    Inclusive percentile rank:
      100 * (# peers with value <= subject_value) / N
    """

    by_group: dict[tuple[int, str], list[ComparisonInputRow]] = defaultdict(list)

    for row in rows:
        by_group[(row.year, row.metric)].append(row)

    output: dict[tuple[int, str, str], float] = {}

    for (year, metric), group_rows in by_group.items():
        values = [g.value for g in group_rows if g.value is not None]

        n = len(values)

        for group_row in group_rows:
            le_count = sum(1 for v in values if v <= group_row.value)
            output[(group_row.year, group_row.geo_id, group_row.metric)] = (
                100 * (le_count / n) if n > 0 else 0.0
            )

    return output


def _build_trend_gap_map(
    rows: list[ComparisonInputRow],
) -> dict[tuple[int, str, str], tuple[float | None, str | None, str | None, bool]]:
    """
    trend_gap per (geo_id, metric):
      gap_t = value_t - benchmark_value_t
      trend_gap = gap_last - gap_first
    Value is assigned to all rows in that geo/metric series.
    """

    by_series: dict[tuple[str, str], list[ComparisonInputRow]] = defaultdict(list)

    for row in rows:
        by_series[(row.geo_id, row.metric)].append(row)

    output: dict[
        tuple[int, str, str], tuple[float | None, str | None, str | None, bool]
    ] = {}

    for (geo_id, metric), series_rows in by_series.items():
        ordered_rows = sorted(series_rows, key=lambda x: x.year)

        if len(ordered_rows) < 2:
            for row in ordered_rows:
                output[(row.year, row.geo_id, row.metric)] = (
                    None,
                    None,
                    "INSUFFICIENT_TIMEPOINTS",
                    False,
                )
            continue

        first_gap = ordered_rows[0].value - ordered_rows[0].benchmark_value
        last_gap = ordered_rows[-1].value - ordered_rows[-1].benchmark_value
        delta_gap = last_gap - first_gap

        for row in ordered_rows:
            output[(row.year, row.geo_id, row.metric)] = (
                delta_gap,
                "trend_gap uses first and last available year in series",
                None,
                True,
            )
    return output


def compute_comparison_metrics(
    request: ComparisonMetricComputeRequest,
) -> list[ComparisonMetricRow]:
    """Compute the comparison metrics for the given request."""

    # 1) request-level prechecks (fail fast)
    if not request.plan.join_keys:
        raise ValueError("join_keys must be non-empty")

    if not request.plan.derived_metrics:
        raise ValueError("derived_metrics must be non-empty")

    if not request.rows:
        raise ValueError("rows must be non-empty")

    for derived_metric in request.plan.derived_metrics:
        if derived_metric not in SUPPORTED_DERIVED_METRICS:
            raise ValueError(f"derived_metric {derived_metric} is not supported")

    # 2) enforce join-key contract for this deterministic compute boundary
    expected_join_keys = {"year", "geo_id"}
    if set(request.plan.join_keys) != expected_join_keys:
        raise ValueError(
            "join_keys must be exactly ['year', 'geo_id'] for metric compute"
        )

    # 3) row-level fail-closed validation against plan scope
    allowed_years = set(request.plan.query_years)
    allowed_subject_geos = set(request.plan.subject_geos)

    for row in request.rows:
        if row.metric != request.plan.metric:
            raise ValueError("row metric does not match plan.metric")
        if row.year not in allowed_years:
            raise ValueError("row year is outside plan.query_years")
        if row.geo_id not in allowed_subject_geos:
            raise ValueError("row geo_id is outside plan.subject_geos")

    # 4) deterministic row ordering (input) and build input maps
    rows_sorted = _sorted_rows(request.rows)

    results: list[ComparisonMetricRow] = []

    percentile_map = _build_percentile_map(rows_sorted)

    trend_gap_map = _build_trend_gap_map(rows_sorted)

    rank_map = _build_rank_map(
        rows_sorted,
        dataset=request.plan.dataset,
        geo_level=request.plan.subject_geo_level,
    )

    # 5) nested loop: every row x every requested derived metric and compute the value
    for row in rows_sorted:
        for derived_metric in request.plan.derived_metrics:
            value: float | None = None
            note: str | None = None
            error: str | None = None
            success = True

            key = (row.year, row.geo_id, row.metric)

            # --- metric-specific branches ---
            if derived_metric == "difference":
                value = _compute_difference(row.value, row.benchmark_value)

            elif derived_metric == "pct_difference":
                pct = _compute_pct_difference(row.value, row.benchmark_value)
                if pct is None:
                    success = False
                    error = "DIVISION_BY_ZERO"
                else:
                    value = pct

            elif derived_metric == "rank":
                value = rank_map.get((row.year, row.geo_id, row.metric))

                if value is None:
                    success = False
                    error = "MISSING_RANK_GROUP_KEY"
                    note = "rank value not found"

            elif derived_metric == "percentile":
                value = percentile_map.get(key, None)

                if value is None:
                    success = False
                    error = "MISSING_GROUP_CONTEXT"
                    note = "percentile value not found"

            elif derived_metric == "trend_gap":
                tg_value, tg_note, tg_error, tg_success = trend_gap_map.get(
                    key, (None, None, "MISSING_SERIES_CONTEXT", False)
                )
                value = tg_value
                note = tg_note
                error = tg_error
                success = tg_success

            else:
                success = False
                error = "UNSUPPORTED_DERIVED_METRIC"
            results.append(
                ComparisonMetricRow(
                    year=row.year,
                    geo_id=row.geo_id,
                    metric=row.metric,
                    derived_metric=derived_metric,
                    value=value,
                    subject_value=row.value,
                    benchmark_value=row.benchmark_value,
                    note=note,
                    error=error,
                    success=success,
                )
            )
    # deterministic output ordering
    return sorted(results, key=lambda r: (r.year, r.geo_id, r.metric, r.derived_metric))
