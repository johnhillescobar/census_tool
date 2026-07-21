from typing import Any

from langchain_core.runnables import RunnableConfig

from src.services.temporal_policy import resolve_temporal_intent
from src.state.types import CensusState, FinalResponseState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch


def temporal_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Workflow to resolve the temporal intent."""
    user_question = state.messages[-1]["content"]
    existing_plan = state.plan
    upstream_clarification = bool(existing_plan and existing_plan.requires_clarification)
    temporal_resolution = resolve_temporal_intent(user_question)

    if upstream_clarification:
        return CensusGraphPatch(
            plan=existing_plan.model_copy(update={"requires_clarification": True}),
            logs=["temporal: skipped (clarification required)"],
        ).as_langgraph_update()

    if temporal_resolution.status == "clarification_required":
        prompt = temporal_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return CensusGraphPatch(
            plan=(existing_plan or WorkflowPlan()).model_copy(
                update={"temporal": temporal_resolution, "requires_clarification": True}
            ),
            final=FinalResponseState(
                answer_text=clarification_text,
                clarification_type="temporal",
                reason_code=temporal_resolution.reason_code,
            ),
            logs=[f"temporal: clarification required ({temporal_resolution.reason_code})"],
        ).as_langgraph_update()

    return CensusGraphPatch(
        plan=(existing_plan or WorkflowPlan()).model_copy(
            update={"temporal": temporal_resolution, "requires_clarification": False}
        ),
        logs=["temporal: resolved"],
    ).as_langgraph_update()
