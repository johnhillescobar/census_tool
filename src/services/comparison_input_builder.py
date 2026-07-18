import re
from statistics import mean
from typing import Any

from src.domain.agent_output_contract import is_placeholder_geo_id, plan_uses_placeholder_geos
from src.domain.comparison_artifacts import (
    METRIC_VARIABLE_MAP,
    ComparisonCensusObservation,
    ComparisonInputRow,
    ComparisonInputRowBuildRequest,
)
from src.domain.comparison_plan import ComparisonPlan

YEAR_COLUMN_NAMES = {"year", "Year", "YEAR"}
GEO_ID_COLUMN_NAMES = {"geo_id", "geoId", "GEO_ID"}
NATIONAL_GEO_IDS = {"us:1", "1", "0100000US", "0100000US0000000000"}


def _normalize_header(value: Any) -> str:
    return str(value).strip()


def _parse_year_from_url(url: str) -> int | None:
    match = re.search(r"/(\d{4})/", url)
    if match:
        return int(match.group(1))
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _find_column_index(headers: list[str], candidates: set[str]) -> int | None:
    normalized = [_normalize_header(header) for header in headers]
    for index, header in enumerate(normalized):
        if header in candidates:
            return index
    return None


def _resolve_value_column_index(headers: list[str], plan: ComparisonPlan) -> int:
    variable_code = METRIC_VARIABLE_MAP.get(plan.metric)
    normalized = [_normalize_header(header) for header in headers]

    if variable_code and variable_code in normalized:
        return normalized.index(variable_code)

    for index, header in enumerate(normalized):
        if header.endswith("E") and header.startswith("B"):
            return index

    raise ValueError(f"unable to locate value column for metric {plan.metric}")


def _build_geo_id_from_row(headers: list[str], row: list[Any]) -> str | None:
    normalized = [_normalize_header(header) for header in headers]
    geo_id_index = _find_column_index(normalized, GEO_ID_COLUMN_NAMES)
    if geo_id_index is not None:
        geo_id = _normalize_header(row[geo_id_index])
        return geo_id or None

    state_index = _find_column_index(normalized, {"state"})
    county_index = _find_column_index(normalized, {"county"})
    if state_index is not None and county_index is not None:
        state = _normalize_header(row[state_index]).zfill(2)
        county = _normalize_header(row[county_index]).zfill(3)
        return f"{state}{county}"

    state_index = _find_column_index(normalized, {"state"})
    if state_index is not None and county_index is None:
        state = _normalize_header(row[state_index]).zfill(2)
        return state

    return None


def _resolve_year_for_row(
    headers: list[str],
    row: list[Any],
    *,
    fallback_year: int | None,
) -> int | None:
    normalized = [_normalize_header(header) for header in headers]
    year_index = _find_column_index(normalized, YEAR_COLUMN_NAMES)
    if year_index is not None:
        year_value = _parse_float(row[year_index])
        if year_value is not None:
            return int(year_value)
    return fallback_year


def extract_observations_from_census_data(
    census_data: dict[str, Any],
    plan: ComparisonPlan,
) -> list[ComparisonCensusObservation]:
    """Extract typed census observations from agent tabular census_data."""

    if not census_data.get("success"):
        raise ValueError("census_data.success must be true")

    rows = census_data.get("data") or []
    if len(rows) < 2:
        raise ValueError("census_data.data must include headers and at least one row")

    headers = [_normalize_header(header) for header in rows[0]]
    value_index = _resolve_value_column_index(headers, plan)
    fallback_year = _parse_year_from_url(str(census_data.get("url", "")))

    observations: list[ComparisonCensusObservation] = []

    for raw_row in rows[1:]:
        if not isinstance(raw_row, list):
            raise ValueError("census_data rows must be list values")

        geo_id = _build_geo_id_from_row(headers, raw_row)
        if geo_id is None:
            continue

        year = _resolve_year_for_row(headers, raw_row, fallback_year=fallback_year)
        if year is None:
            raise ValueError("unable to resolve year for census_data row")

        value = _parse_float(raw_row[value_index])
        if value is None:
            raise ValueError(f"unable to parse metric value for geo_id {geo_id}")

        observations.append(
            ComparisonCensusObservation(
                year=year,
                geo_id=geo_id,
                metric=plan.metric,
                value=value,
                geo_level=plan.subject_geo_level,
            )
        )

    if not observations:
        raise ValueError("no observations extracted from census_data")

    return sorted(observations, key=lambda item: (item.year, item.geo_id))


def _is_single_benchmark(plan: ComparisonPlan) -> bool:
    return len(plan.benchmark_geos) == 1 and not any(is_placeholder_geo_id(geo_id) for geo_id in plan.benchmark_geos)


def _is_peer_group(plan: ComparisonPlan) -> bool:
    if plan.subject_geos == plan.benchmark_geos and len(plan.subject_geos) > 1:
        return True
    if plan_uses_placeholder_geos(plan):
        return (
            plan.benchmark_geo_level == plan.subject_geo_level
            and plan.benchmark_geo_level is not None
            and any(geo_id.startswith("peer:") for geo_id in plan.benchmark_geos)
        )
    return False


def _effective_subject_geos(
    plan: ComparisonPlan,
    observations: list[ComparisonCensusObservation],
) -> list[str]:
    if not any(is_placeholder_geo_id(geo_id) for geo_id in plan.subject_geos):
        return list(plan.subject_geos)

    allowed_years = set(plan.query_years)
    subject_candidates = sorted(
        {
            observation.geo_id
            for observation in observations
            if observation.metric == plan.metric
            and observation.year in allowed_years
            and observation.geo_id not in NATIONAL_GEO_IDS
            and not is_placeholder_geo_id(observation.geo_id)
        }
    )
    if not subject_candidates:
        raise ValueError("no observations to resolve placeholder subject geos")
    return subject_candidates


def _resolve_benchmark_geo_id(
    plan: ComparisonPlan,
    *,
    year: int,
    observations: list[ComparisonCensusObservation],
    effective_subject_geos: list[str],
) -> str:
    if _is_peer_group(plan):
        raise ValueError("peer-group benchmark does not use a single benchmark geo_id")

    if _is_single_benchmark(plan):
        return plan.benchmark_geos[0]

    subject_set = set(effective_subject_geos)
    candidates = sorted(
        {
            observation.geo_id
            for observation in observations
            if observation.year == year
            and observation.metric == plan.metric
            and observation.geo_id not in subject_set
            and not is_placeholder_geo_id(observation.geo_id)
        }
    )
    if not candidates:
        raise ValueError("unable to resolve placeholder benchmark geo from observations")
    return candidates[0]


def _lookup_observation(
    observations: list[ComparisonCensusObservation],
    *,
    year: int,
    geo_id: str,
    metric: str,
) -> ComparisonCensusObservation | None:
    for observation in observations:
        if observation.year == year and observation.geo_id == geo_id and observation.metric == metric:
            return observation
    return None


def _peer_group_benchmark_value(
    observations: list[ComparisonCensusObservation],
    *,
    year: int,
    metric: str,
    subject_geo_id: str,
    allowed_geos: set[str],
) -> float:
    peer_values = [
        observation.value
        for observation in observations
        if observation.year == year
        and observation.metric == metric
        and observation.geo_id in allowed_geos
        and observation.geo_id != subject_geo_id
    ]
    if not peer_values:
        raise ValueError(f"missing peer-group benchmark observations for geo_id {subject_geo_id}")
    return mean(peer_values)


def build_comparison_input_rows(
    request: ComparisonInputRowBuildRequest,
) -> list[ComparisonInputRow]:
    """
    Build comparison input rows from typed observations and a comparison plan.

    Benchmark pairing rules:
    - Single benchmark geo: all subject rows share that benchmark value for the year.
    - Peer group (subject_geos == benchmark_geos): benchmark_value is peer mean excluding self.
    - Missing benchmark observation: fail closed.
    """

    plan = request.plan
    observations = sorted(request.observations, key=lambda item: (item.year, item.geo_id))

    allowed_years = set(plan.query_years)
    subject_geos = _effective_subject_geos(plan, observations)
    allowed_subject_geos = set(subject_geos)
    allowed_benchmark_geos = set(subject_geos) if _is_peer_group(plan) else set(plan.benchmark_geos)

    output_rows: list[ComparisonInputRow] = []

    for subject_geo_id in sorted(subject_geos):
        for year in sorted(plan.query_years):
            subject_observation = _lookup_observation(
                observations,
                year=year,
                geo_id=subject_geo_id,
                metric=plan.metric,
            )
            if subject_observation is None:
                raise ValueError(f"missing subject observation for geo_id {subject_geo_id} year {year}")

            if year not in allowed_years:
                raise ValueError("observation year is outside plan.query_years")
            if subject_geo_id not in allowed_subject_geos:
                raise ValueError("observation geo_id is outside plan.subject_geos")

            benchmark_value: float | None = None

            if _is_peer_group(plan):
                benchmark_value = _peer_group_benchmark_value(
                    observations,
                    year=year,
                    metric=plan.metric,
                    subject_geo_id=subject_geo_id,
                    allowed_geos=allowed_benchmark_geos,
                )
            elif _is_single_benchmark(plan):
                benchmark_geo_id = plan.benchmark_geos[0]
                benchmark_observation = _lookup_observation(
                    observations,
                    year=year,
                    geo_id=benchmark_geo_id,
                    metric=plan.metric,
                )
                if benchmark_observation is None and benchmark_geo_id in NATIONAL_GEO_IDS:
                    benchmark_observation = next(
                        (
                            observation
                            for observation in observations
                            if observation.year == year
                            and observation.metric == plan.metric
                            and observation.geo_id in NATIONAL_GEO_IDS
                        ),
                        None,
                    )
                if benchmark_observation is None:
                    raise ValueError(f"missing benchmark observation for geo_id {benchmark_geo_id} year {year}")
                benchmark_value = benchmark_observation.value
            else:
                benchmark_geo_id = _resolve_benchmark_geo_id(
                    plan,
                    year=year,
                    observations=observations,
                    effective_subject_geos=subject_geos,
                )
                benchmark_observation = _lookup_observation(
                    observations,
                    year=year,
                    geo_id=benchmark_geo_id,
                    metric=plan.metric,
                )
                if benchmark_observation is None:
                    raise ValueError(f"missing benchmark observation for geo_id {benchmark_geo_id} year {year}")
                benchmark_value = benchmark_observation.value

            output_rows.append(
                ComparisonInputRow(
                    year=year,
                    geo_id=subject_geo_id,
                    metric=plan.metric,
                    value=subject_observation.value,
                    benchmark_value=benchmark_value,
                )
            )

    return sorted(output_rows, key=lambda row: (row.year, row.geo_id))
