import operator
from typing import Annotated, Any, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.benchmark_contract import (
    BenchmarkClarificationRequired,
    BenchmarkResolved,
)
from src.domain.comparison_plan import ComparisonPlan
from src.domain.census_tool_contract import (
    StrictCensusApiResponse,
    no_strict_census_payload,
)
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.temporal_contract import TemporalResolution
from src.domain.comparison_metric_contract import (
    ComparisonMetricRow,
    ComparisonInputRow,
)
from src.domain.variable_metada_contract import VariableLabels
from src.domain.rendered_output_contract import GeneratedFileArtifact
from src.domain.strict_json import (
    ConversationMessage,
    JsonMap,
    empty_json_map,
    merge_json_maps,
)




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
    generated_files: list[GeneratedFileArtifact] = Field(default_factory=list)

    @field_validator("generated_files", mode="before")
    @classmethod
    def _legacy_generated_files_add_success_status(cls, value: Any) -> Any:
        """Pre-2C JSON had success rows without ``status``; discriminate as success."""
        if not isinstance(value, list):
            return value
        out: list[Any] = []
        for item in value:
            if isinstance(item, dict) and item.get("status") is None:
                kind = item.get("kind")
                if kind in ("chart", "table") and "path" in item and "error_code" not in item:
                    out.append({"status": "success", **item})
                else:
                    out.append(item)
            else:
                out.append(item)
        return out


class WorkflowArtifactsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_data: StrictCensusApiResponse = Field(
        default_factory=no_strict_census_payload,
        description="The Census API response (use no_strict_census_payload when absent).",
    )
    variable_labels: VariableLabels = Field(default_factory=VariableLabels)
    data_summary: str = Field(default="", description="The summary of the data.")
    reasoning_trace: str = Field(default="", description="The reasoning trace.")
    comparison_input_rows: list[ComparisonInputRow] = Field(
        default_factory=list, description="The input rows for the comparison."
    )
    comparison_metrics: list[ComparisonMetricRow] = Field(
        default_factory=list, description="The metrics for the comparison."
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_null_census_data(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("census_data") is None:
            out = dict(data)
            out["census_data"] = no_strict_census_payload()
            return out
        return data


def _coerce_artifacts(
    value: WorkflowArtifactsState | None,
) -> WorkflowArtifactsState:
    if value is None:
        return WorkflowArtifactsState()
    return value


def _merge_artifacts(
    existing: WorkflowArtifactsState | None,
    new: WorkflowArtifactsState | None,
) -> WorkflowArtifactsState:
    existing_model = _coerce_artifacts(existing)
    new_model = _coerce_artifacts(new)
    default_model = WorkflowArtifactsState()

    updates = {
        field_name: getattr(new_model, field_name)
        for field_name in new_model.model_fields_set
        if getattr(new_model, field_name) != getattr(default_model, field_name)
    }
    return existing_model.model_copy(update=updates)


# Define the state schema (Annotated reducers are used by LangGraph for append/merge semantics)
class CensusState(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    # Core conversation data
    messages: Annotated[list[ConversationMessage], operator.add] = Field(
        default_factory=list, description="Chat turns; reducer: append"
    )
    original_query: str | None = Field(
        None,
        description="Original user query (preserved for pattern matching); reducer: overwrite",
    )
    intent: JsonMap | None = Field(None, description="Intent analysis; reducer: overwrite")
    geo: JsonMap = Field(
        default_factory=empty_json_map,
        description="Geo resolution; reducer: overwrite",
    )
    candidates: JsonMap = Field(
        default_factory=empty_json_map,
        description="Candidate variables; reducer: overwrite",
    )
    plan: WorkflowPlanState | None = Field(
        None, description="Query plan; reducer: overwrite"
    )
    artifacts: Annotated[WorkflowArtifactsState, _merge_artifacts] = Field(
        default_factory=WorkflowArtifactsState,
        description="Dataset and preview handles; reducer: merge typed artifact fields",
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
    profile: Annotated[JsonMap, merge_json_maps] = Field(
        default_factory=empty_json_map,
        description="User profile; reducer: merge JsonMap roots",
    )
    history: list[JsonMap] = Field(
        default_factory=list, description="Conversation history; reducer: overwrite"
    )
    cache_index: Annotated[JsonMap, merge_json_maps] = Field(
        default_factory=empty_json_map,
        description="Cache index; reducer: merge JsonMap roots",
    )

    @field_validator("geo", "candidates", "profile", "cache_index", mode="before")
    @classmethod
    def _coerce_legacy_dict_maps(cls, value: Any) -> JsonMap:
        if isinstance(value, JsonMap):
            return value
        if isinstance(value, dict):
            return JsonMap.model_validate(value)
        raise TypeError(
            "Expected JsonMap-coercible dict for map channel, "
            f"got {type(value).__name__}"
        )

    @field_validator("intent", mode="before")
    @classmethod
    def _coerce_optional_intent_map(cls, value: Any) -> JsonMap | None:
        if value is None:
            return None
        if isinstance(value, JsonMap):
            return value
        if isinstance(value, dict):
            return JsonMap.model_validate(value)
        raise TypeError(
            "Expected JsonMap-coercible dict for intent, "
            f"got {type(value).__name__}"
        )

    @field_validator("history", mode="before")
    @classmethod
    def _coerce_history_entries(cls, value: Any) -> list[JsonMap]:
        if not isinstance(value, list):
            raise TypeError(f"history must be a list, got {type(value).__name__}")
        out: list[JsonMap] = []
        for item in value:
            if isinstance(item, JsonMap):
                out.append(item)
            elif isinstance(item, dict):
                out.append(JsonMap.model_validate(item))
            else:
                raise TypeError(
                    f"history row must be dict or JsonMap, got {type(item).__name__}"
                )
        return out


class QuerySpec(BaseModel):
    year: int = Field(..., description="Year for the query")
    dataset: str = Field(..., description="Census dataset name")
    variables: List[str] = Field(..., description="List of variable codes to query")
    geo: JsonMap = Field(..., description="Geography filters for the query")
    save_as: str = Field(..., description="Filename to save results as")

    @field_validator("geo", mode="before")
    @classmethod
    def _qs_geo(cls, value: Any) -> JsonMap:
        if isinstance(value, JsonMap):
            return value
        if isinstance(value, dict):
            return JsonMap.model_validate(value)
        raise TypeError(f"geo must coerce to JsonMap, got {type(value).__name__}")


class GeographyEntity(BaseModel):
    name: str = Field(..., description="Name of the geographic entity")
    type: str = Field(..., description="Type: 'city', 'county', 'state', 'tract'")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    context: JsonMap = Field(
        default_factory=empty_json_map, description="Additional context information"
    )
    start_pos: int = Field(..., ge=0, description="Start position in original text")
    end_pos: int = Field(..., ge=0, description="End position in original text")

    @field_validator("context", mode="before")
    @classmethod
    def _entity_context(cls, value: Any) -> JsonMap:
        if isinstance(value, JsonMap):
            return value
        if isinstance(value, dict):
            return JsonMap.model_validate(value)
        raise TypeError(
            "GeographyEntity.context must coerce to JsonMap, "
            f"got {type(value).__name__}"
        )


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
    geocoding_metadata: JsonMap = Field(
        default_factory=empty_json_map, description="API response details"
    )

    @field_validator("geocoding_metadata", mode="before")
    @classmethod
    def _geo_meta(cls, value: Any) -> JsonMap:
        if isinstance(value, JsonMap):
            return value
        if isinstance(value, dict):
            return JsonMap.model_validate(value)
        raise TypeError(
            "ResolvedGeography.geocoding_metadata must coerce to JsonMap, "
            f"got {type(value).__name__}"
        )


class GeographyError(BaseModel):
    error_type: str = Field(
        ..., description="Error type: 'unsupported_level', 'not_found', 'api_error'"
    )
    message: str = Field(..., description="Human-readable error message")
    suggested_alternatives: List[str] = Field(
        default_factory=list, description="Suggested alternative locations or levels"
    )
