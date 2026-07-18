from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PresentationKind(Enum):
    """Deterministic UI routing derived from state, not agent text."""

    CLARIFICATION = "clarification"
    NON_CENSUS_OR_EMPTY = "non_census_or_empty"
    NARRATIVE_ONLY = "narrative_only"
    SINGLE_VALUE = "single_value"
    TIME_SERIES = "time_series"
    TABLE = "table"


class PresentationRouting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PresentationKind
    reason: str = Field(default="", description="Short deterministic explanation for logs/tests.")
