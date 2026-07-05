import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.domain.comparison_artifacts import ComparisonInputRowBuildRequest
from src.domain.comparison_plan import ComparisonPlan
from src.llm.intent_enhancer import generate_llm_answer
from src.services.agent_plan_context import build_agent_plan_context
from src.services.comparison_input_builder import (
    build_comparison_input_rows,
    extract_observations_from_census_data,
)
from src.state.types import CensusState

logger = logging.getLogger(__name__)


def _build_comparison_input_rows_from_result(
    census_data: dict[str, Any],
    comparison_plan: ComparisonPlan,
) -> list[dict[str, Any]]:
    observations = extract_observations_from_census_data(census_data, comparison_plan)
    rows = build_comparison_input_rows(
        ComparisonInputRowBuildRequest(
            plan=comparison_plan,
            observations=observations,
        )
    )
    return [row.model_dump() for row in rows]


def agent_reasoning_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    user_question = state.messages[-1]["content"]

    intent = state.intent or {"is_census": True, "topic": "general"}

    if state.plan and state.plan.requires_clarification:
        return {"logs": ["agent: skipped (clarification required)"]}

    plan_context = build_agent_plan_context(state.plan)
    if plan_context is None:
        plan_log = "agent: no plan context attached"
    elif plan_context.has_comparison_plan:
        plan_log = "agent: plan context attached (comparison)"
    else:
        plan_log = "agent: plan context attached (temporal only)"

    comparison_plan = plan_context.comparison if plan_context is not None else None

    agent = CensusQueryAgent()
    result = agent.solve(
        user_query=user_question,
        intent=intent,
        plan_context=plan_context,
    )

    answer_text = result.get("answer_text", "")

    if not answer_text or len(answer_text.strip()) < 20:
        census_data = result.get("census_data", {})
        data_summary = result.get("data_summary", "")
        geo_context = state.geo or {}

        if census_data and data_summary:
            logger.info(
                "answer_text is too short, generating rich answer from census data"
            )
            try:
                generated_answer = generate_llm_answer(
                    user_question=user_question,
                    data_summary=data_summary,
                    geo_context=geo_context,
                    intent=intent,
                )
                if generated_answer:
                    answer_text = generated_answer
                    logger.info("Successfully generated rich answer_text")
            except Exception as exc:
                logger.warning("Failed to generate rich answer_text: %s", exc)

    footnotes = result.get("footnotes", [])
    if not footnotes:
        from src.services.footnote_generator import generate_footnotes

        logger.info("Generating footnotes (not provided by agent)")
        try:
            footnotes = generate_footnotes(
                census_data=result.get("census_data", {}),
                data_summary=result.get("data_summary", ""),
                reasoning_trace=result.get("reasoning_trace", ""),
            )
            logger.info("Generated %s footnotes", len(footnotes))
        except Exception as exc:
            logger.warning("Failed to generate footnotes: %s", exc)
            footnotes = [
                "Source: U.S. Census Bureau, American Community Survey.",
                "This tool is for informational purposes only. Verify critical data at census.gov.",
            ]

    artifacts: dict[str, Any] = {
        "census_data": result.get("census_data", {}),
        "data_summary": result.get("data_summary", ""),
        "reasoning_trace": result.get("reasoning_trace", ""),
    }

    agent_rows = [
        row.model_dump() if hasattr(row, "model_dump") else row
        for row in result.get("comparison_input_rows", [])
    ]
    if agent_rows:
        artifacts["comparison_input_rows"] = agent_rows
    else:
        census_data = result.get("census_data", {})
        if (
            comparison_plan is not None
            and isinstance(census_data, dict)
            and census_data.get("success")
        ):
            try:
                comparison_input_rows = _build_comparison_input_rows_from_result(
                    census_data,
                    comparison_plan,
                )
                artifacts["comparison_input_rows"] = comparison_input_rows
                logger.info(
                    "agent: built %s comparison_input_rows from census_data",
                    len(comparison_input_rows),
                )
            except Exception as exc:
                logger.warning(
                    "agent: failed to build comparison_input_rows, metrics node will skip: %s",
                    exc,
                )

    return {
        "artifacts": artifacts,
        "final": {
            "answer_text": answer_text,
            "charts_needed": result.get("charts_needed", []),
            "tables_needed": result.get("tables_needed", []),
            "footnotes": footnotes,
        },
        "logs": [plan_log, "agent: completed reasoning with data"],
    }
