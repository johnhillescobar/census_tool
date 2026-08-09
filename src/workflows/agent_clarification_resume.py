"""Agent-driven clarification resume (CENSUS-44 Phase 3)."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.services.agent_plan_context import build_agent_clarification_context
from src.services.clarification_selection import extract_clarification_selection
from src.services.geography_clarification_resume import (
    GeographyResumeResult,
    TableResumePrepared,
    apply_agent_clarification_selection,
    render_pending_clarification_retry,
)
from src.services.plan_validation_exhaust_clarification import (
    PlanValidationExhaustResumePrepared,
    apply_plan_validation_exhaust_selection,
    is_plan_validation_exhaust_pending,
)
from src.state.types import CensusState
from src.workflows.geography import continue_table_clarification_from_prepared
from src.workflows.graph_patch import CensusGraphPatch, FinalResponseState

logger = logging.getLogger(__name__)


def _patch_from_geography_resume_result(
    result: GeographyResumeResult,
    *,
    pending_trace_id: str,
    requested_slot: str,
) -> dict[str, Any]:
    if result.status == "resolved":
        return CensusGraphPatch(
            plan=result.plan,
            geo=result.geography,
            logs=[f"agent_clarification_resume: resolved from trace {pending_trace_id}"],
        ).as_langgraph_update()

    pending = result.plan.pending_geography_clarification
    reason_code = (
        "GEOGRAPHY_CANCELLED"
        if result.status == "cancelled"
        else pending.reason_code
        if pending is not None
        else "CLARIFICATION_REQUIRED"
    )
    clarification_type = "table" if requested_slot == "table" else "geography"
    return CensusGraphPatch(
        plan=result.plan,
        final=FinalResponseState(
            answer_text=result.answer_text,
            clarification_type=clarification_type,
            reason_code=reason_code,
            trace_id=pending_trace_id,
        ),
        logs=[f"agent_clarification_resume: clarification {result.status} ({reason_code})"],
    ).as_langgraph_update()


def agent_clarification_resume_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Run agent clarification turn, then apply grounded selection without legacy text parsing."""

    plan = state.plan
    if plan is None or plan.pending_geography_clarification is None:
        raise ValueError("agent clarification resume requires pending clarification context")

    clarification_context = build_agent_clarification_context(plan)
    if clarification_context is None:
        raise ValueError("agent clarification resume requires clarification context")

    pending = plan.pending_geography_clarification
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

    selection = extract_clarification_selection(agent_result)
    if selection is None:
        retry = render_pending_clarification_retry(
            plan,
            "I could not map your reply to a grounded option. Please choose one of the listed options.",
        )
        resume_update = _patch_from_geography_resume_result(
            retry,
            pending_trace_id=pending.trace_id,
            requested_slot=pending.requested_slot,
        )
    else:
        if is_plan_validation_exhaust_pending(pending):
            resolved = apply_plan_validation_exhaust_selection(plan, selection.candidate_id)
        else:
            resolved = apply_agent_clarification_selection(plan, selection.candidate_id)
        if isinstance(resolved, PlanValidationExhaustResumePrepared):
            resume_update = CensusGraphPatch(
                plan=resolved.plan,
                logs=[f"agent_clarification_resume: plan validation exhaust selection applied ({pending.trace_id})"],
            ).as_langgraph_update()
        elif isinstance(resolved, TableResumePrepared):
            resume_update = continue_table_clarification_from_prepared(state, config, resolved)
        else:
            resume_update = _patch_from_geography_resume_result(
                resolved,
                pending_trace_id=pending.trace_id,
                requested_slot=pending.requested_slot,
            )

    existing_logs = resume_update.get("logs") or []
    resume_update["logs"] = [*agent_logs, *existing_logs]
    resume_update.setdefault("artifacts", {})
    resume_update["artifacts"]["clarification_trace"] = agent_result.get("reasoning_trace", "")
    resume_update["artifacts"]["clarification_summary"] = agent_result.get("data_summary", "")
    if selection is not None:
        resume_update["artifacts"]["clarification_selection"] = {
            "candidate_id": selection.candidate_id,
            "option_id": selection.option_id,
            "label": selection.label,
        }
    return resume_update


__all__ = ["agent_clarification_resume_node"]
