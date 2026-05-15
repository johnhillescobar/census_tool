from langchain_core.runnables import RunnableConfig
import re

from src.services.benchmark_policy import resolve_benchmark_intent
from src.state.types import (
    BenchmarkNotApplicable,
    CensusState,
    FinalResponseState,
    WorkflowPlanState,
)
from src.workflows.graph_patch import CensusGraphPatch


COMPARE_PATTERN = re.compile(r"\b(compare|vs|versus|against)\b", re.IGNORECASE)


def benchmark_node(state: CensusState, config: RunnableConfig) -> dict[str, object]:
    user_question = state.messages[-1].content
    existing_plan = state.plan
    temporal_plan = existing_plan.temporal if existing_plan else None

    # Non-comparison requests should not be forced through benchmark clarification.
    if not COMPARE_PATTERN.search(user_question or ""):
        return CensusGraphPatch(
            plan=WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=BenchmarkNotApplicable(reason="no_comparison_intent"),
                requires_clarification=False,
            ),
            logs=["benchmark: skipped (no comparison intent)"],
        ).as_langgraph_update()

    benchmark_resolution = resolve_benchmark_intent(user_question)

    if benchmark_resolution.status == "clarification_required":
        prompt = benchmark_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return CensusGraphPatch(
            plan=WorkflowPlanState(
                temporal=temporal_plan,
                benchmark=benchmark_resolution,
                requires_clarification=True,
            ),
            final=FinalResponseState(
                answer_text=clarification_text,
            ),
            logs=[
                f"benchmark: clarification required ({benchmark_resolution.reason_code})"
            ],
        ).as_langgraph_update()

    return CensusGraphPatch(
        plan=WorkflowPlanState(
            temporal=temporal_plan,
            benchmark=benchmark_resolution,
            requires_clarification=False,
        ),
        logs=["benchmark: resolved"],
    ).as_langgraph_update()
