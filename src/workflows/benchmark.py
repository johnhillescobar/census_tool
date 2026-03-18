from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.services.benchmark_policy import resolve_benchmark_intent
from src.state.types import CensusState


class BenchmarkPlan(BaseModel):
    temporal: dict[str, Any] | None = None
    benchmark: dict[str, Any]
    requires_clarification: bool


class FinalPayload(BaseModel):
    answer_text: str
    charts_needed: list[dict[str, Any]] = Field(default_factory=list)
    tables_needed: list[dict[str, Any]] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)


class BenchmarkNodeOutput(BaseModel):
    plan: BenchmarkPlan
    final: FinalPayload | None = None
    logs: list[str] = Field(default_factory=list)


def benchmark_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    user_question = state.messages[-1]["content"]
    benchmark_resolution = resolve_benchmark_intent(user_question)

    existing_plan = state.plan or {}
    temporal_plan = existing_plan.get("temporal")

    if benchmark_resolution.status == "clarification_required":
        prompt = benchmark_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        output = BenchmarkNodeOutput(
            plan=BenchmarkPlan(
                temporal=temporal_plan,
                benchmark=benchmark_resolution.model_dump(),
                requires_clarification=True,
            ),
            final=FinalPayload(
                answer_text=clarification_text,
            ),
            logs=[
                f"benchmark: clarification required ({benchmark_resolution.reason_code})"
            ],
        )
        return output.model_dump(exclude_none=True)

    output = BenchmarkNodeOutput(
        plan=BenchmarkPlan(
            temporal=temporal_plan,
            benchmark=benchmark_resolution.model_dump(),
            requires_clarification=False,
        ),
        logs=["benchmark: resolved"],
    )
    return output.model_dump(exclude_none=True)
