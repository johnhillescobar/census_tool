from typing import Any

from langchain_core.runnables import RunnableConfig

from src.services.temporal_policy import resolve_temporal_intent
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan


def temporal_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Workflow to resolve the temporal intent."""
    user_question = state.messages[-1]["content"]
    temporal_resolution = resolve_temporal_intent(user_question)

    if temporal_resolution.status == "clarification_required":
        prompt = temporal_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return {
            "plan": WorkflowPlan(
                temporal=temporal_resolution,
                requires_clarification=True,
            ),
            "final": {
                "answer_text": clarification_text,
            },
            "logs": [
                f"temporal: clarification required ({temporal_resolution.reason_code})"
            ],
        }

    return {
        "plan": WorkflowPlan(
            temporal=temporal_resolution,
            requires_clarification=False,
        ),
        "logs": ["temporal: resolved"],
    }
