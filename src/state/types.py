from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


# Define the state schema
class CensusState(BaseModel):
    # Core conversation data
    messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chat turns; reducer: append"
    )
    original_query: Optional[str] = Field(
        None, description="Original user query (preserved for pattern matching); reducer: overwrite"
    )
    intent: Optional[Dict[str, Any]] = Field(
        None, description="Intent analysis; reducer: overwrite"
    )
    geo: Dict[str, Any] = Field(
        default_factory=dict, description="Geo resolution; reducer: overwrite"
    )
    candidates: Dict[str, Any] = Field(
        default_factory=dict, description="Candidate variables; reducer: overwrite"
    )
    plan: Optional[Dict[str, Any]] = Field(
        None, description="Query plan; reducer: overwrite"
    )
    artifacts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dataset and preview handles; reducer: merge dictionaries",
    )
    final: Optional[Dict[str, Any]] = Field(
        None, description="Final answer; reducer: overwrite"
    )

    # System data
    logs: List[str] = Field(
        default_factory=list, description="System logs; reducer: append"
    )
    error: Optional[str] = Field(None, description="Error message; reducer: overwrite")
    summary: Optional[str] = Field(
        None, description="Message summary; reducer: overwrite"
    )

    # Memory and persistence
    profile: Dict[str, Any] = Field(
        default_factory=dict, description="User profile; reducer: merge dictionaries"
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Conversation history; reducer: append"
    )
    cache_index: Dict[str, Any] = Field(
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
    requested_level: Optional[str] = Field(
        None, description="Requested geography level"
    )
    state_context: Optional[str] = Field(None, description="State context if provided")
    user_id: Optional[str] = Field(None, description="User ID for caching")


class ResolvedGeography(BaseModel):
    level: str = Field(..., description="Resolved geography level")
    filters: Dict[str, str] = Field(
        default_factory=dict, description="Census API filters"
    )
    display_name: str = Field(..., description="Human-readable location name")
    fips_codes: Dict[str, str] = Field(
        ..., default_factory=dict, description="FIPS codes for the location"
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
