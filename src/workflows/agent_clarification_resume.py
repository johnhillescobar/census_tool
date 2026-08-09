"""Agent-driven clarification resume (CENSUS-44 Phase 3)."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.services.agent_plan_context import build_agent_clarification_context
from src.state.types import CensusState
from src.workflows.geography import geography_resume_node

logger = logging.getLogger(__name__)


def agent_clarification_resume_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Run agent clarification turn, then validate selection via geography resume harness."""

    plan = state.plan
    if plan is None or plan.pending_geography_clarification is None:
        raise ValueError("agent clarification resume requires pending clarification context")

    clarification_context = build_agent_clarification_context(plan)
    if clarification_context is None:
        raise ValueError("agent clarification resume requires clarification context")

    user_reply = state.messages[-1]["content"]
    intent = state.intent or {"is_census": True, "topic": "general"}

    agent = CensusQueryAgent(mode="planning")
    agent_result = agent.solve(
        user_query=user_reply,
        intent=intent,
        clarification_context=clarification_context,
    )

    if agent.offline_mode:
        agent_logs = ["agent_clarification_resume: harness resume (agent offline)"]
    else:
        agent_logs = [
            "agent_clarification_resume: completed clarification turn",
            f"agent_clarification_resume: {agent_result.get('reasoning_trace', '')}",
        ]
        logger.info("agent_clarification_resume: completed clarification turn")

    # Harness validates the user reply against preserved evidence (geography_clarification_resume).
    resume_update = geography_resume_node(state, config)
    existing_logs = resume_update.get("logs") or []
    resume_update["logs"] = [*agent_logs, *existing_logs]
    resume_update.setdefault("artifacts", {})
    resume_update["artifacts"]["clarification_trace"] = agent_result.get("reasoning_trace", "")
    resume_update["artifacts"]["clarification_summary"] = agent_result.get("data_summary", "")
    return resume_update


__all__ = ["agent_clarification_resume_node"]
