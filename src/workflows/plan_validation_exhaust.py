"""Prepare agent clarification when plan validation retries exhaust (CENSUS-50)."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.services.plan_validation_exhaust_clarification import prepare_plan_validation_exhaust_clarification
from src.state.types import CensusState
from src.workflows.graph_patch import CensusGraphPatch


def plan_validation_exhaust_node(state: CensusState, config: RunnableConfig) -> dict:
    _ = config
    plan = state.plan
    if plan is None:
        raise ValueError("plan validation exhaust requires an active workflow plan")

    user_question = state.messages[-1]["content"]
    update = prepare_plan_validation_exhaust_clarification(plan, original_query=user_question)
    return CensusGraphPatch(plan=update["plan"], logs=update["logs"]).as_langgraph_update()


__all__ = ["plan_validation_exhaust_node"]
