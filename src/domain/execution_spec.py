"""Deterministic execution obligations derived from planning artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.geography_contract import GeographyIntent
from src.domain.temporal_contract import TemporalIntent

_TABLE_ONLY_NATIONAL_GEO_FOR = {"us": "1"}


def default_national_geography_intent(*, requested_text: str | None = None) -> GeographyIntent:
    """National scope used when a validated table-only plan has no geography evidence."""
    return GeographyIntent(
        level="nation",
        geo_for=dict(_TABLE_ONLY_NATIONAL_GEO_FOR),
        geo_in={},
        display_name="United States",
        source="explicit",
        requested_text=requested_text,
        census_token="us",
    )


def resolve_execution_geography(plan_context: AgentPlanContext) -> GeographyIntent | None:
    """Return resolved geography for execution, including table-only national default."""
    if plan_context.geography is not None:
        return plan_context.geography
    if plan_context.grounded_plan is not None and plan_context.grounded_plan.geography is None:
        requested_text = plan_context.temporal.requested_text if plan_context.temporal is not None else None
        return default_national_geography_intent(requested_text=requested_text)
    return None


class ExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geography: GeographyIntent
    temporal: TemporalIntent
    query_years: list[int] = Field(default_factory=list)
    requires_time_series: bool = False
    output_shape: str = "single_or_series"


def build_execution_spec(plan_context: AgentPlanContext) -> ExecutionSpec | None:
    if plan_context.temporal is None:
        return None

    geography = resolve_execution_geography(plan_context)
    if geography is None:
        return None

    temporal = plan_context.temporal
    query_years: list[int] = []
    requires_time_series = False

    if temporal.mode == "range" and temporal.start_year is not None and temporal.end_year is not None:
        query_years = list(range(temporal.start_year, temporal.end_year + 1))
        requires_time_series = True
        output_shape = "time_series"
    elif temporal.mode == "point_in_time" and temporal.anchor_year is not None:
        query_years = [temporal.anchor_year]
        output_shape = "single_value"
    elif temporal.mode == "latest_available":
        output_shape = "single_value"
    else:
        output_shape = "single_or_series"

    return ExecutionSpec(
        geography=geography,
        temporal=temporal,
        query_years=query_years,
        requires_time_series=requires_time_series,
        output_shape=output_shape,
    )
