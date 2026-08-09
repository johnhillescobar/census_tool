from pydantic import BaseModel, ConfigDict, Field

from src.domain.retrieval_plan import RetrievalEvidence
from src.state.workflow_plan import GeographyClarificationSlot, PendingGeographyOption


class AgentClarificationContext(BaseModel):
    """Checkpointed clarification state exposed to the agent on turn 2 (CENSUS-44)."""

    model_config = ConfigDict(extra="forbid")

    original_query: str
    requested_slot: GeographyClarificationSlot
    pending_options: list[PendingGeographyOption] = Field(default_factory=list)
    retrieval_evidence: list[RetrievalEvidence] = Field(default_factory=list)
    reason_code: str
    trace_id: str


__all__ = ["AgentClarificationContext"]
