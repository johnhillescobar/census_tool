from src.domain.presentation_contract import PresentationKind, PresentationRouting
from src.state.types import CensusState


def _headers_from_legacy_census_data(census_data: dict) -> list[str]:
    data = census_data.get("data", [])
    if isinstance(data, list) and data and isinstance(data[0], list):
        return [str(header) for header in data[0]]
    return []


def _row_count_from_legacy_census_data(census_data: dict) -> int:
    data = census_data.get("data", [])
    if isinstance(data, list) and data:
        return max(0, len(data) - 1)
    return 0


def _has_yearish_columns(headers: list[str]) -> bool:
    lowered = {header.lower() for header in headers}
    return bool(lowered & {"year", "time", "date"})


def compute_presentation_routing(state: CensusState) -> PresentationRouting:
    plan = state.plan
    final = state.final or {}
    artifacts = state.artifacts or {}

    if plan is not None and getattr(plan, "requires_clarification", False):
        return PresentationRouting(
            kind=PresentationKind.CLARIFICATION,
            reason="plan.requires_clarification",
        )

    if not final:
        return PresentationRouting(
            kind=PresentationKind.NON_CENSUS_OR_EMPTY,
            reason="missing_final",
        )

    census_data = artifacts.get("census_data", {})
    if not isinstance(census_data, dict) or not census_data.get("success"):
        return PresentationRouting(
            kind=PresentationKind.NARRATIVE_ONLY,
            reason="no_successful_census_data",
        )

    headers = _headers_from_legacy_census_data(census_data)
    row_count = _row_count_from_legacy_census_data(census_data)
    charts_needed = final.get("charts_needed", [])
    line_requested = any(
        isinstance(chart, dict) and chart.get("type") == "line"
        for chart in charts_needed
    )

    if row_count <= 1 and not _has_yearish_columns(headers) and not line_requested:
        return PresentationRouting(
            kind=PresentationKind.SINGLE_VALUE,
            reason="single_row_no_year_column",
        )

    if _has_yearish_columns(headers) or line_requested:
        return PresentationRouting(
            kind=PresentationKind.TIME_SERIES,
            reason="year_column_or_line_chart",
        )

    return PresentationRouting(kind=PresentationKind.TABLE, reason="default_tabular")
