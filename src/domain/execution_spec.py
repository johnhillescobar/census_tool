"""Deterministic execution obligations derived from planning artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.agent_plan_context import AgentPlanContext
from src.domain.geography_contract import GeographyIntent
from src.domain.temporal_contract import TemporalIntent


class ExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geography: GeographyIntent
    temporal: TemporalIntent
    query_years: list[int] = Field(default_factory=list)
    requires_time_series: bool = False
    output_shape: str = "single_or_series"


def build_execution_spec(plan_context: AgentPlanContext) -> ExecutionSpec | None:
    if plan_context.temporal is None or plan_context.geography is None:
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
        geography=plan_context.geography,
        temporal=temporal,
        query_years=query_years,
        requires_time_series=requires_time_series,
        output_shape=output_shape,
    )
