import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agents.census_query_agent import CensusQueryAgent
from src.domain.comparison_artifacts import ComparisonInputRowBuildRequest
from src.domain.comparison_plan import ComparisonPlan
from src.llm.intent_enhancer import generate_llm_answer
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

    # Agent expects intent dict - create basic one if not exists
    intent = state.intent or {"is_census": True, "topic": "general"}

    plan = state.plan or {}
    if plan.get("requires_clarification"):
        return {"logs": ["agent: skipped (clarification required)"]}

    comparison_plan: ComparisonPlan | None = None
    comparison_plan_raw = plan.get("comparison")
    if comparison_plan_raw:
        try:
            comparison_plan = ComparisonPlan.model_validate(comparison_plan_raw)
        except Exception as exc:
            logger.warning("agent: invalid comparison plan, continuing without plan: %s", exc)

    agent = CensusQueryAgent()
    result = agent.solve(
        user_query=user_question,
        intent=intent,
        comparison_plan=comparison_plan,
    )

    # Get answer_text from agent result
    answer_text = result.get("answer_text", "")

    # Fallback: If answer_text is missing, empty, or too short, generate it from the census data
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
            except Exception as e:
                logger.warning(f"Failed to generate rich answer_text: {e}")

    # Generate footnotes if not provided by agent
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
            logger.info(f"Generated {len(footnotes)} footnotes")
        except Exception as e:
            logger.warning(f"Failed to generate footnotes: {e}")
            # Provide minimal fallback footnotes
            footnotes = [
                "Source: U.S. Census Bureau, American Community Survey.",
                "This tool is for informational purposes only. Verify critical data at census.gov.",
            ]

    artifacts: dict[str, Any] = {
        "census_data": result.get("census_data", {}),
        "data_summary": result.get("data_summary", ""),
        "reasoning_trace": result.get("reasoning_trace", ""),
    }

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
        "logs": ["agent: completed reasoning with data"],
    }
