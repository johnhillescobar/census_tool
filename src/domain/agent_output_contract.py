from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .comparison_input_contract import ComparisonInputRow
from .comparison_plan import ComparisonPlan


def is_placeholder_geo_id(geo_id: str) -> bool:
    """Return True when a geo_id is an unresolved planning placeholder."""
    if geo_id.endswith(":unknown"):
        return True
    if geo_id.startswith("peer:"):
        return True
    return geo_id.startswith("subject:")


class CensusDataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    data: list[list[Any]] = Field(default_factory=list)
    variables: dict[str, str] | None = None


class AgentPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_data: CensusDataPayload
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
                raise ValueError(
                    f"comparison_input_rows contains unresolved placeholder geo_id: {row.geo_id}"
                )
        return self


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
        if row.geo_id not in plan.subject_geos:
            raise ValueError("row geo_id is outside plan.subject_geos")
        if is_placeholder_geo_id(row.geo_id):
            raise ValueError(
                f"comparison_input_rows contains unresolved placeholder geo_id: {row.geo_id}"
            )
        validated.append(row)
    return validated
