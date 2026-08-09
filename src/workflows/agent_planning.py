import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.services.agent_plan_context import build_agent_planning_context
from src.state.types import CensusState

logger = logging.getLogger(__name__)


def agent_planning_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Run retrieval-only agent planning after temporal resolution (CENSUS-40 Phase 1)."""

    user_question = state.messages[-1]["content"]
    intent = state.intent or {"is_census": True, "topic": "general"}

    if state.plan and state.plan.requires_clarification:
        return {"logs": ["agent_planning: skipped (clarification required)"]}

    plan_context = build_agent_planning_context(state.plan)
    if plan_context is None:
        return {"logs": ["agent_planning: skipped (no temporal context)"]}

    agent = CensusQueryAgent(mode="planning")
    result = agent.solve(
        user_query=user_question,
        intent=intent,
        plan_context=plan_context,
    )

    logger.info("agent_planning: completed retrieval planning turn")
    return {
        "artifacts": {
            "planning_trace": result.get("reasoning_trace", ""),
            "planning_summary": result.get("data_summary", ""),
        },
        "logs": ["agent_planning: completed retrieval planning turn"],
    }
