import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

import config
from src.agents.census_query_agent import CensusQueryAgent
from src.domain.clarification_templates import render_slot_clarification
from src.domain.geography_contract import ClarificationOption
from src.services.agent_clarification_copy import build_agent_clarification_copy
from src.services.agent_plan_context import (
    build_agent_clarification_context,
    build_agent_planning_context,
    should_skip_agent_for_upstream_clarification,
)
from src.services.agent_planning_artifacts import collect_planning_artifacts
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch

logger = logging.getLogger(__name__)


def _is_turn1_clarification_planning(plan: WorkflowPlan | None) -> bool:
    return (
        config.CENSUS_AGENT_TURN1_PLANNING
        and plan is not None
        and plan.pending_geography_clarification is not None
        and plan.requires_clarification
    )


def _run_turn1_clarification_planning(state: CensusState, intent: dict[str, Any]) -> dict[str, Any]:
    """Emit turn-1 clarification copy via agent_planning (CENSUS-44b)."""
    plan = state.plan
    if plan is None or plan.pending_geography_clarification is None:
        raise ValueError("turn-1 clarification planning requires pending clarification context")

    clarification_context = build_agent_clarification_context(plan)
    if clarification_context is None:
        raise ValueError("turn-1 clarification planning requires clarification context")

    agent = CensusQueryAgent(mode="planning")
    if agent.offline_mode:
        answer_text = build_agent_clarification_copy(clarification_context)
        source = "deterministic"
        logs = ["agent_planning: turn-1 clarification copy (agent offline)"]
    else:
        agent_result = agent.compose_clarification_prompt(clarification_context)
        answer_text = agent_result.get("answer_text") or build_agent_clarification_copy(clarification_context)
        source = "agent"
        logs = [
            "agent_planning: turn-1 clarification copy via agent",
            f"agent_planning: {agent_result.get('reasoning_trace', '')}",
        ]
        logger.info("agent_planning: emitted turn-1 clarification copy")

    pending = plan.pending_geography_clarification
    prompt = render_slot_clarification(
        pending.reason_code,
        [ClarificationOption(option_id=option.option_id, label=option.label) for option in pending.options],
        requested_slot=pending.requested_slot,
    )
    final = dict(state.final or {})
    final["answer_text"] = answer_text
    final.setdefault("clarification_type", "table" if pending.requested_slot == "table" else "geography")
    final.setdefault("reason_code", prompt.reason_code)
    final.setdefault("trace_id", pending.trace_id)

    update = CensusGraphPatch(final=final, logs=logs).as_langgraph_update()
    update["artifacts"] = {"clarification_prompt_source": source, "turn1_planning_authority": True}
    return update


def agent_planning_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Run retrieval-only agent planning after temporal resolution (CENSUS-40 Phase 1)."""

    _ = config
    user_question = state.messages[-1]["content"]
    intent = state.intent or {"is_census": True, "topic": "general"}

    if _is_turn1_clarification_planning(state.plan):
        return _run_turn1_clarification_planning(state, intent)

    if should_skip_agent_for_upstream_clarification(state.plan):
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
