import operator
from typing import Annotated, Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.benchmark_contract import (
    BenchmarkClarificationRequired,
    BenchmarkResolved,
)
from src.domain.comparison_plan import ComparisonPlan
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.temporal_contract import TemporalResolution


def _merge_dict(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer for dict state channels: merge new into existing (last writer wins per key)."""
    if existing is None:
        return new if new is not None else {}
    if new is None:
        return existing
    out = dict(existing)
    out.update(new)
    return out


class BenchmarkNotApplicable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_applicable"] = Field(default="not_applicable")
    reason: str = Field(..., description="Why benchmark logic was skipped.")


BenchmarkWorkflowState = Annotated[
    BenchmarkResolved | BenchmarkClarificationRequired | BenchmarkNotApplicable,
    Field(discriminator="status"),
]


class WorkflowPlanState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temporal: TemporalResolution | None = None
    benchmark: BenchmarkWorkflowState | None = None
    comparison: ComparisonPlan | None = None
    requires_clarification: bool = False


class FinalResponseState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_text: str = ""
    charts_needed: list[FinalChartSpec] = Field(default_factory=list)
    tables_needed: list[FinalTableSpec] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)


class WorkflowArtifactsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_data: dict[str, Any] = Field(default_factory=dict)
    data_summary: str = ""
    reasoning_trace: str = ""
    comparison_input_rows: list[dict[str, Any]] = Field(default_factory=list)
    comparison_metrics: list[dict[str, Any]] = Field(default_factory=list)


def _coerce_artifacts(
    value: WorkflowArtifactsState | Dict[str, Any] | None,
) -> WorkflowArtifactsState:
    if value is None:
        return WorkflowArtifactsState()
    if isinstance(value, WorkflowArtifactsState):
        return value
    return WorkflowArtifactsState.model_validate(value)


def _merge_artifacts(
    existing: WorkflowArtifactsState | Dict[str, Any] | None,
    new: WorkflowArtifactsState | Dict[str, Any] | None,
) -> WorkflowArtifactsState:
    existing_model = _coerce_artifacts(existing)
    new_model = _coerce_artifacts(new)

    merged = existing_model.model_dump()
    merged.update(new_model.model_dump(exclude_defaults=True))
    return WorkflowArtifactsState.model_validate(merged)


# Define the state schema (Annotated reducers are used by LangGraph for append/merge semantics)
class CensusState(BaseModel):
    # Core conversation data
    messages: Annotated[List[Dict[str, Any]], operator.add] = Field(
        default_factory=list, description="Chat turns; reducer: append"
    )
    original_query: str | None = Field(
        None,
        description="Original user query (preserved for pattern matching); reducer: overwrite",
    )
    intent: Dict[str, Any] | None = Field(
        None, description="Intent analysis; reducer: overwrite"
    )
    geo: Dict[str, Any] = Field(
        default_factory=dict, description="Geo resolution; reducer: overwrite"
    )
    candidates: Dict[str, Any] = Field(
        default_factory=dict, description="Candidate variables; reducer: overwrite"
    )
    plan: WorkflowPlanState | None = Field(
        None, description="Query plan; reducer: overwrite"
    )
    artifacts: Annotated[WorkflowArtifactsState, _merge_artifacts] = Field(
        default_factory=WorkflowArtifactsState,
        description="Dataset and preview handles; reducer: merge dictionaries",
    )
    final: FinalResponseState | None = Field(
        None, description="Final answer; reducer: overwrite"
    )

    # System data
    logs: Annotated[List[str], operator.add] = Field(
        default_factory=list, description="System logs; reducer: append"
    )
    error: str | None = Field(None, description="Error message; reducer: overwrite")
    summary: str | None = Field(None, description="Message summary; reducer: overwrite")

    # Memory and persistence
    profile: Annotated[Dict[str, Any], _merge_dict] = Field(
        default_factory=dict, description="User profile; reducer: merge dictionaries"
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Conversation history; reducer: overwrite"
    )
    cache_index: Annotated[Dict[str, Any], _merge_dict] = Field(
        default_factory=dict, description="Cache index; reducer: merge dictionaries"
    )


class QuerySpec(BaseModel):
    year: int = Field(..., description="Year for the query")
    dataset: str = Field(..., description="Census dataset name")
    variables: List[str] = Field(..., description="List of variable codes to query")
    geo: Dict[str, Any] = Field(..., description="Geography filters for the query")
    save_as: str = Field(..., description="Filename to save results as")


class GeographyEntity(BaseModel):
    name: str = Field(..., description="Name of the geographic entity")
    type: str = Field(..., description="Type: 'city', 'county', 'state', 'tract'")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context information"
    )
    start_pos: int = Field(..., ge=0, description="Start position in original text")
    end_pos: int = Field(..., ge=0, description="End position in original text")


class GeographyRequest(BaseModel):
    raw_text: str = Field(..., description="Original user query text")
    entities: List[GeographyEntity] = Field(
        default_factory=list, description="Extracted geography entities"
    )
    requested_level: str | None = Field(None, description="Requested geography level")
    state_context: str | None = Field(None, description="State context if provided")
    user_id: str | None = Field(None, description="User ID for caching")


class ResolvedGeography(BaseModel):
    level: str = Field(..., description="Resolved geography level")
    filters: Dict[str, str] = Field(
        default_factory=dict, description="Census API filters"
    )
    display_name: str = Field(..., description="Human-readable location name")
    fips_codes: Dict[str, str] = Field(
        default_factory=dict, description="FIPS codes for the location"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    note: str = Field(default="", description="Additional notes about the resolution")
    geocoding_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="API response details"
    )


class GeographyError(BaseModel):
    error_type: str = Field(
        ..., description="Error type: 'unsupported_level', 'not_found', 'api_error'"
    )
    message: str = Field(..., description="Human-readable error message")
    suggested_alternatives: List[str] = Field(
        default_factory=list, description="Suggested alternative locations or levels"
    )
