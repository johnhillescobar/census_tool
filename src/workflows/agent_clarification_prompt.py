"""Turn-1 agent-readable clarification copy (CENSUS-44 increment 2)."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.domain.clarification_templates import render_slot_clarification
from src.domain.geography_contract import ClarificationOption
from src.services.agent_clarification_copy import build_agent_clarification_copy
from src.services.agent_plan_context import build_agent_clarification_context
from src.state.types import CensusState

logger = logging.getLogger(__name__)


def agent_clarification_prompt_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Replace raw table_N clarification output with readable labels + recommended default."""
    _ = config
    plan = state.plan
    if plan is None or plan.pending_geography_clarification is None:
        raise ValueError("agent clarification prompt requires pending clarification context")

    clarification_context = build_agent_clarification_context(plan)
    if clarification_context is None:
        raise ValueError("agent clarification prompt requires clarification context")

    agent = CensusQueryAgent(mode="planning")
    if agent.offline_mode:
        answer_text = build_agent_clarification_copy(clarification_context)
        source = "deterministic"
        logs = ["agent_clarification_prompt: deterministic copy (agent offline)"]
    else:
        agent_result = agent.compose_clarification_prompt(clarification_context)
        answer_text = agent_result.get("answer_text") or build_agent_clarification_copy(clarification_context)
        source = "agent"
        logs = [
            "agent_clarification_prompt: agent-generated clarification copy",
            f"agent_clarification_prompt: {agent_result.get('reasoning_trace', '')}",
        ]
        logger.info("agent_clarification_prompt: emitted agent clarification copy")

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

    return {
        "final": final,
        "artifacts": {"clarification_prompt_source": source},
        "logs": logs,
    }


__all__ = ["agent_clarification_prompt_node"]
