from typing import Any

from langchain_core.runnables import RunnableConfig

from src.services.temporal_policy import resolve_temporal_intent
from src.state.types import CensusState, FinalResponseState, WorkflowPlanState


def temporal_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Workflow to resolve the temporal intent.

    Args:
        user_text: The text to resolve the temporal intent for.

    Returns:
        A TemporalResolution object.
    """

    user_question = state.messages[-1]["content"]
    temporal_resolution = resolve_temporal_intent(user_question)

    if temporal_resolution.status == "clarification_required":
        prompt = temporal_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return {
            "plan": WorkflowPlanState(
                temporal=temporal_resolution,
                requires_clarification=True,
            ),
            "final": FinalResponseState(
                answer_text=clarification_text,
            ),
            "logs": [
                f"temporal: clarification required ({temporal_resolution.reason_code})"
            ],
        }

    return {
        "plan": WorkflowPlanState(
            temporal=temporal_resolution,
            requires_clarification=False,
        ),
        "logs": ["temporal: resolved"],
    }
