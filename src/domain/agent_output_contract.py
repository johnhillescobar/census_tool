from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .census_tool_contract import StrictCensusApiResponse
from .comparison_input_contract import ComparisonInputRow
from .comparison_plan import ComparisonPlan


def is_placeholder_geo_id(geo_id: str) -> bool:
    """Return True when a geo_id is an unresolved planning placeholder."""
    if geo_id.endswith(":unknown"):
        return True
    if geo_id.startswith("peer:"):
        return True
    return geo_id.startswith("subject:")


def plan_uses_placeholder_geos(plan: ComparisonPlan) -> bool:
    """Return True when the comparison plan still has unresolved geo placeholders."""
    return any(is_placeholder_geo_id(geo_id) for geo_id in plan.subject_geos) or any(
        is_placeholder_geo_id(geo_id) for geo_id in plan.benchmark_geos
    )


class CensusDataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    data: list[list[Any]] = Field(default_factory=list)
    variables: dict[str, str] | None = None
    url: str | None = None


AgentCensusData = StrictCensusApiResponse | CensusDataPayload


class AgentPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_data: AgentCensusData
    data_summary: str
    reasoning_trace: str
    answer_text: str
    charts_needed: list[dict[str, Any]] = Field(default_factory=list)
    tables_needed: list[dict[str, Any]] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
    comparison_input_rows: list[ComparisonInputRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_no_placeholder_rows(self) -> "AgentPlanOutput":
        for row in self.comparison_input_rows:
            if is_placeholder_geo_id(row.geo_id):
                raise ValueError(f"comparison_input_rows contains unresolved placeholder geo_id: {row.geo_id}")
        return self


def strict_census_response_to_legacy_payload(
    response: StrictCensusApiResponse,
) -> CensusDataPayload:
    """Adapt a validated strict Census response to the current workflow payload."""
    data = [
        response.headers,
        *[[record.values.get(header, "") for header in response.headers] for record in response.records],
    ]
    variables = {header: header for header in response.headers}
    url = None
    if response.request is not None:
        url = f"https://api.census.gov/data/{response.request.year}/{response.request.dataset}"
    return CensusDataPayload(
        success=response.success,
        data=data,
        variables=variables,
        url=url,
    )


def agent_output_to_legacy_dict(output: AgentPlanOutput) -> dict[str, Any]:
    """
    Serialize typed agent output for existing workflow state.

    This is the explicit compatibility boundary; upstream validation keeps strict
    Census responses typed until this final handoff.
    """
    census_data = output.census_data
    if isinstance(census_data, StrictCensusApiResponse):
        legacy_census_data = strict_census_response_to_legacy_payload(census_data)
    else:
        legacy_census_data = census_data

    return {
        "census_data": legacy_census_data.model_dump(),
        "data_summary": output.data_summary,
        "reasoning_trace": output.reasoning_trace,
        "answer_text": output.answer_text,
        "charts_needed": output.charts_needed,
        "tables_needed": output.tables_needed,
        "footnotes": output.footnotes,
        "comparison_input_rows": [row.model_dump() for row in output.comparison_input_rows],
    }


def validate_comparison_rows_for_plan(
    rows: list[ComparisonInputRow],
    plan: ComparisonPlan,
) -> list[ComparisonInputRow]:
    """Validate agent-emitted rows align with the active ComparisonPlan."""
    validated: list[ComparisonInputRow] = []
    for row in rows:
        if row.metric != plan.metric:
            raise ValueError("row metric does not match plan.metric")
        if row.year not in plan.query_years:
            raise ValueError("row year is outside plan.query_years")
        if not plan_uses_placeholder_geos(plan) and row.geo_id not in plan.subject_geos:
            raise ValueError("row geo_id is outside plan.subject_geos")
        if is_placeholder_geo_id(row.geo_id):
            raise ValueError(f"comparison_input_rows contains unresolved placeholder geo_id: {row.geo_id}")
        validated.append(row)
    return validated
