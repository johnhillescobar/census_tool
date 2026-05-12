import logging

from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.state.types import (
    CensusState,
    FinalResponseState,
    WorkflowArtifactsState,
)
from src.agents.census_query_agent import CensusQueryAgent
from src.llm.intent_enhancer import generate_llm_answer


logger = logging.getLogger(__name__)


def agent_reasoning_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    user_question = state.messages[-1]["content"]

    # Agent expects intent dict - create basic one if not exists
    intent = state.intent or {"is_census": True, "topic": "general"}

    plan = state.plan
    if plan and plan.requires_clarification:
        return {"logs": ["agent: skipped (clarification required)"]}

    agent = CensusQueryAgent()
    result = agent.solve(user_query=user_question, intent=intent)

    # Get answer_text from agent result
    answer_text = result.answer_text

    # Fallback: If answer_text is missing, empty, or too short, generate it from the census data
    if not answer_text or len(answer_text.strip()) < 20:
        census_data = result.census_data
        data_summary = result.data_summary
        geo_context = state.geo or {}

        if census_data.success and data_summary:
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
    footnotes = result.footnotes
    if not footnotes:
        from src.services.footnote_generator import generate_footnotes

        logger.info("Generating footnotes (not provided by agent)")
        try:
            footnotes = generate_footnotes(
                census_data=result.census_data,
                data_summary=result.data_summary,
                reasoning_trace=result.reasoning_trace,
            )
            logger.info(f"Generated {len(footnotes)} footnotes")
        except Exception as e:
            logger.warning(f"Failed to generate footnotes: {e}")
            # Provide minimal fallback footnotes
            footnotes = [
                "Source: U.S. Census Bureau, American Community Survey.",
                "This tool is for informational purposes only. Verify critical data at census.gov.",
            ]

    existing_final = state.final or FinalResponseState()

    return {
        "artifacts": WorkflowArtifactsState(
            census_data=result.census_data,
            variable_labels=result.variable_labels,
            data_summary=result.data_summary,
            reasoning_trace=result.reasoning_trace,
        ),
        "final": FinalResponseState(
            answer_text=answer_text,
            charts_needed=result.charts_needed,
            tables_needed=result.tables_needed,
            footnotes=footnotes,
            generated_files=existing_final.generated_files,
        ),
        "logs": ["agent: completed reasoning with data"],
    }
