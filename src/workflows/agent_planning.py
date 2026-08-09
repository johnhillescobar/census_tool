import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.services.agent_plan_context import build_agent_planning_context
from src.services.agent_planning_artifacts import collect_planning_artifacts
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch

logger = logging.getLogger(__name__)


def agent_planning_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Run retrieval-only agent planning after temporal resolution (CENSUS-40 Phase 1)."""

    user_question = state.messages[-1]["content"]
    intent = state.intent or {"is_census": True, "topic": "general"}

    if state.plan and state.plan.requires_clarification:
        return {"logs": ["agent_planning: skipped (clarification required)"]}

    if state.plan and state.plan.plan_validation_failures:
        codes = ", ".join(failure.reason_code for failure in state.plan.plan_validation_failures)
        logger.info("agent_planning: retry after validation failures (%s)", codes)

    plan_context = build_agent_planning_context(state.plan)
    if plan_context is None:
        return {"logs": ["agent_planning: skipped (no temporal context)"]}

    agent = CensusQueryAgent(mode="planning")
    result = agent.solve(
        user_query=user_question,
        intent=intent,
        plan_context=plan_context,
    )

    if agent.offline_mode:
        log_msg = "agent_planning: skipped (no LLM credentials)"
        logger.info(log_msg)
        update = CensusGraphPatch(logs=[log_msg]).as_langgraph_update()
        update["artifacts"] = {
            "planning_trace": result.get("reasoning_trace", ""),
            "planning_summary": result.get("data_summary", ""),
        }
        return update

    existing = state.plan or WorkflowPlan()
    evidence_items, proposed_selection = collect_planning_artifacts(result.get("intermediate_steps"))
    plan_updates: dict[str, Any] = {}
    if evidence_items:
        plan_updates["retrieval_evidence"] = evidence_items
    if proposed_selection is not None:
        plan_updates["proposed_selection"] = proposed_selection

    updated_plan = existing.model_copy(update=plan_updates) if plan_updates else existing
    logs = ["agent_planning: completed retrieval planning turn"]
    if proposed_selection is not None:
        logs.append("agent_planning: captured grounded selection proposal")
    elif evidence_items:
        logs.append("agent_planning: captured retrieval evidence without proposal")

    logger.info("agent_planning: completed retrieval planning turn")
    update = CensusGraphPatch(plan=updated_plan, logs=logs).as_langgraph_update()
    update["artifacts"] = {
        "planning_trace": result.get("reasoning_trace", ""),
        "planning_summary": result.get("data_summary", ""),
    }
    return update
