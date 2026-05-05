from src.domain.presentation_contract import PresentationKind, PresentationRouting
from src.state.types import CensusState, FinalResponseState


def _headers(cd) -> list[str]:
    return list(cd.headers) if cd else []


def _has_yearish_columns(headers: list[str]) -> bool:
    h = {x.lower() for x in headers}
    return bool(h & {"year", "time", "date"})


def compute_presentation_routing(state: CensusState) -> PresentationRouting:
    plan = state.plan
    final = state.final
    artifacts = state.artifacts

    if plan is not None and getattr(plan, "requires_clarification", False):
        return PresentationRouting(
            kind=PresentationKind.CLARIFICATION,
            reason="plan.requires_clarification",
        )

    if final is None or not isinstance(final, FinalResponseState):
        return PresentationRouting(
            kind=PresentationKind.NON_CENSUS_OR_EMPTY,
            reason="missing_final",
        )

    cd = artifacts.census_data if artifacts else None
    if cd is None or not cd.success:
        return PresentationRouting(
            kind=PresentationKind.NARRATIVE_ONLY,
            reason="no_successful_census_data",
        )

    headers = _headers(cd)
    n = cd.row_count
    line_requested = any(c.type == "line" for c in (final.charts_needed or []))

    if n <= 1 and not _has_yearish_columns(headers) and not line_requested:
        return PresentationRouting(
            kind=PresentationKind.SINGLE_VALUE,
            reason="single_row_no_year_column",
        )

    if (
        _has_yearish_columns(headers)
        or line_requested
        or (
            plan is not None
            and plan.temporal is not None
            and getattr(plan.temporal, "resolution", None) is not None
        )
    ):
        return PresentationRouting(
            kind=PresentationKind.TIME_SERIES,
            reason="year_column_or_line_chart_or_temporal",
        )

    return PresentationRouting(
        kind=PresentationKind.TABLE,
        reason="default_tabular",
    )
