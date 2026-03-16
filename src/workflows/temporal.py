from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.services.temporal_policy import resolve_temporal_intent
from src.state.types import CensusState


class TemporalPlan(BaseModel):
    temporal: dict[str, Any]
    requires_clarification: bool


class FinalPayload(BaseModel):
    answer_text: str
    charts_needed: list[dict[str, Any]] = Field(default_factory=list)
    tables_needed: list[dict[str, Any]] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)


class TemporalNodeOutput(BaseModel):
    plan: TemporalPlan
    final: FinalPayload | None = None
    logs: list[str] = Field(default_factory=list)


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
        output = TemporalNodeOutput(
            plan=TemporalPlan(
                temporal=temporal_resolution.model_dump(),
                requires_clarification=True,
            ),
            final=FinalPayload(
                answer_text=clarification_text,
            ),
            logs=[
                f"temporal: clarification required ({temporal_resolution.reason_code})"
            ],
        )
        return output.model_dump(exclude_none=True)

    output = TemporalNodeOutput(
        plan=TemporalPlan(
            temporal=temporal_resolution.model_dump(),
            requires_clarification=False,
        ),
        logs=["temporal: resolved"],
    )
    return output.model_dump(exclude_none=True)
