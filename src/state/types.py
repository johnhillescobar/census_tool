import operator
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.agent_output_contract import CensusDataPayload
from src.domain.comparison_artifacts import ComparisonInputRow, ComparisonMetricArtifactRow
from src.state.workflow_plan import WorkflowPlan


def _merge_dict(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Reducer for dict state channels: merge new into existing (last writer wins per key)."""
    if existing is None:
        return new if new is not None else {}
    if new is None:
        return existing
    out = dict(existing)
    out.update(new)
    return out


class FinalResponseState(BaseModel):
    """Typed view of the final-answer state channel."""

    model_config = ConfigDict(extra="forbid")

    answer_text: str = ""
    charts_needed: list[dict[str, Any]] = Field(default_factory=list)
    tables_needed: list[dict[str, Any]] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)


class WorkflowArtifactsState(BaseModel):
    """Typed view of artifact fields emitted by workflow nodes."""

    model_config = ConfigDict(extra="forbid")

    census_data: CensusDataPayload | None = None
    data_summary: str = ""
    reasoning_trace: str = ""
    comparison_input_rows: list[ComparisonInputRow] = Field(default_factory=list)
    comparison_metrics: list[ComparisonMetricArtifactRow] = Field(default_factory=list)


def final_state_to_update(final: FinalResponseState) -> dict[str, Any]:
    """Compatibility projection for the current dict-shaped state channel."""
    return final.model_dump(exclude_none=True)


def artifacts_state_to_update(artifacts: WorkflowArtifactsState) -> dict[str, Any]:
    """Compatibility projection for the current dict-shaped artifacts channel."""
    return artifacts.model_dump(exclude_none=True, exclude_defaults=True)


# Define the state schema (Annotated reducers are used by LangGraph for append/merge semantics)
class CensusState(BaseModel):
    # Core conversation data
    messages: Annotated[list[dict[str, Any]], operator.add] = Field(
        default_factory=list, description="Chat turns; reducer: append"
    )
    original_query: str | None = Field(
        None,
        description="Original user query (preserved for pattern matching); reducer: overwrite",
    )
    intent: dict[str, Any] | None = Field(
        None, description="Intent analysis; reducer: overwrite"
    )
    geo: dict[str, Any] = Field(
        default_factory=dict, description="Geo resolution; reducer: overwrite"
    )
    candidates: dict[str, Any] = Field(
        default_factory=dict, description="Candidate variables; reducer: overwrite"
    )
    plan: WorkflowPlan | None = Field(
        None, description="Query plan; reducer: overwrite"
    )
    artifacts: Annotated[dict[str, Any], _merge_dict] = Field(
        default_factory=dict,
        description="Dataset and preview handles; reducer: merge dictionaries",
    )
    final: dict[str, Any] | None = Field(
        None, description="Final answer; reducer: overwrite"
    )

    # System data
    logs: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="System logs; reducer: append"
    )
    error: str | None = Field(None, description="Error message; reducer: overwrite")
    summary: str | None = Field(
        None, description="Message summary; reducer: overwrite"
    )

    # Memory and persistence
    profile: Annotated[dict[str, Any], _merge_dict] = Field(
        default_factory=dict, description="User profile; reducer: merge dictionaries"
    )
    history: list[dict[str, Any]] = Field(
        default_factory=list, description="Conversation history; reducer: overwrite"
    )
    cache_index: Annotated[dict[str, Any], _merge_dict] = Field(
        default_factory=dict, description="Cache index; reducer: merge dictionaries"
    )


class QuerySpec(BaseModel):
    year: int = Field(..., description="Year for the query")
    dataset: str = Field(..., description="Census dataset name")
    variables: list[str] = Field(..., description="List of variable codes to query")
    geo: dict[str, Any] = Field(..., description="Geography filters for the query")
    save_as: str = Field(..., description="Filename to save results as")


class GeographyEntity(BaseModel):
    name: str = Field(..., description="Name of the geographic entity")
    type: str = Field(..., description="Type: 'city', 'county', 'state', 'tract'")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context information"
    )
    start_pos: int = Field(..., ge=0, description="Start position in original text")
    end_pos: int = Field(..., ge=0, description="End position in original text")


class GeographyRequest(BaseModel):
    raw_text: str = Field(..., description="Original user query text")
    entities: list[GeographyEntity] = Field(
        default_factory=list, description="Extracted geography entities"
    )
    requested_level: str | None = Field(
        None, description="Requested geography level"
    )
    state_context: str | None = Field(None, description="State context if provided")
    user_id: str | None = Field(None, description="User ID for caching")


class ResolvedGeography(BaseModel):
    level: str = Field(..., description="Resolved geography level")
    filters: dict[str, str] = Field(
        default_factory=dict, description="Census API filters"
    )
    display_name: str = Field(..., description="Human-readable location name")
    fips_codes: dict[str, str] = Field(
        default_factory=dict, description="FIPS codes for the location"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    note: str = Field(default="", description="Additional notes about the resolution")
    geocoding_metadata: dict[str, Any] = Field(
        default_factory=dict, description="API response details"
    )


class GeographyError(BaseModel):
    error_type: str = Field(
        ..., description="Error type: 'unsupported_level', 'not_found', 'api_error'"
    )
    message: str = Field(..., description="Human-readable error message")
    suggested_alternatives: list[str] = Field(
        default_factory=list, description="Suggested alternative locations or levels"
    )
