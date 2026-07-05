from typing import Any
import re

from langchain_core.runnables import RunnableConfig

from src.services.benchmark_policy import resolve_benchmark_intent
from src.state.types import CensusState
from src.state.workflow_plan import BenchmarkNotApplicable, WorkflowPlan

COMPARE_PATTERN = re.compile(r"\b(compare|vs|versus|against)\b", re.IGNORECASE)


def benchmark_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    user_question = state.messages[-1]["content"]
    existing_plan = state.plan
    temporal = existing_plan.temporal if existing_plan else None

    if not COMPARE_PATTERN.search(user_question or ""):
        return {
            "plan": WorkflowPlan(
                temporal=temporal,
                benchmark=BenchmarkNotApplicable(
                    reason="no_comparison_intent",
                ),
                requires_clarification=False,
            ),
            "logs": ["benchmark: skipped (no comparison intent)"],
        }

    benchmark_resolution = resolve_benchmark_intent(user_question)

    if benchmark_resolution.status == "clarification_required":
        prompt = benchmark_resolution.clarification_prompt
        option_lines = [f"{o.option_id}: {o.label}" for o in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return {
            "plan": WorkflowPlan(
                temporal=temporal,
                benchmark=benchmark_resolution,
                requires_clarification=True,
            ),
            "final": {
                "answer_text": clarification_text,
            },
            "logs": [
                f"benchmark: clarification required ({benchmark_resolution.reason_code})"
            ],
        }

    return {
        "plan": WorkflowPlan(
            temporal=temporal,
            benchmark=benchmark_resolution,
            requires_clarification=False,
        ),
        "logs": ["benchmark: resolved"],
    }
