from typing import Any

from langchain_core.runnables import RunnableConfig

from src.services.geography_policy import resolve_geography_intent
from src.state.types import CensusState, FinalResponseState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch


def geography_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Resolve geography before temporal/benchmark planning."""
    user_question = state.messages[-1]["content"]
    profile_default = state.profile.get("default_geo") if state.profile else None
    resolution = resolve_geography_intent(
        user_question,
        profile_default_geo=profile_default,
    )

    if resolution.status == "clarification_required":
        prompt = resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return CensusGraphPatch(
            plan=WorkflowPlan(
                geography=resolution,
                requires_clarification=True,
            ),
            final=FinalResponseState(answer_text=clarification_text),
            logs=[f"geography: clarification required ({resolution.reason_code})"],
        ).as_langgraph_update()

    return CensusGraphPatch(
        plan=WorkflowPlan(
            geography=resolution,
            requires_clarification=False,
        ),
        geo=resolution.geography,
        logs=[f"geography: resolved ({resolution.geography.source})"],
    ).as_langgraph_update()
