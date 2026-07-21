import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.services.benchmark_policy import resolve_benchmark_intent
from src.state.types import CensusState, FinalResponseState
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch

COMPARE_PATTERN = re.compile(r"\b(compare|ompare|vs|versus|against)\b", re.IGNORECASE)


def benchmark_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    user_question = state.messages[-1]["content"]
    existing_plan = state.plan
    upstream_clarification = bool(existing_plan and existing_plan.requires_clarification)

    if upstream_clarification:
        return CensusGraphPatch(
            plan=existing_plan.model_copy(update={"requires_clarification": True}),
            logs=["benchmark: skipped (clarification required)"],
        ).as_langgraph_update()

    if not COMPARE_PATTERN.search(user_question or ""):
        return CensusGraphPatch(
            plan=(existing_plan or WorkflowPlan()).model_copy(
                update={
                    "benchmark": BenchmarkNotApplicable(reason="no_comparison_intent"),
                    "requires_clarification": False,
                }
            ),
            logs=["benchmark: skipped (no comparison intent)"],
        ).as_langgraph_update()

    benchmark_resolution = resolve_benchmark_intent(user_question)

    if benchmark_resolution.status == "clarification_required":
        prompt = benchmark_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return CensusGraphPatch(
            plan=(existing_plan or WorkflowPlan()).model_copy(
                update={"benchmark": benchmark_resolution, "requires_clarification": True}
            ),
            final=FinalResponseState(answer_text=clarification_text),
            logs=[f"benchmark: clarification required ({benchmark_resolution.reason_code})"],
        ).as_langgraph_update()

    return CensusGraphPatch(
        plan=(existing_plan or WorkflowPlan()).model_copy(
            update={"benchmark": benchmark_resolution, "requires_clarification": False}
        ),
        logs=["benchmark: resolved"],
    ).as_langgraph_update()
