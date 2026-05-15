import logging

from langchain_core.runnables import RunnableConfig

from src.domain.strict_json import DEFAULT_AGENT_INTENT, as_json_map
from src.state.types import (
    CensusState,
    FinalResponseState,
    WorkflowArtifactsState,
)
from src.workflows.graph_patch import CensusGraphPatch
from src.agents.census_query_agent import CensusQueryAgent
from src.llm.intent_enhancer import generate_llm_answer


logger = logging.getLogger(__name__)


def agent_reasoning_node(state: CensusState, config: RunnableConfig) -> dict[str, object]:
    user_question = state.messages[-1].content

    if state.intent is None:
        intent_channel = DEFAULT_AGENT_INTENT
    else:
        intent_channel = as_json_map(state.intent)

    geo_for_llm = as_json_map(state.geo)

    plan = state.plan
    if plan and plan.requires_clarification:
        return CensusGraphPatch(
            logs=["agent: skipped (clarification required)"],
        ).as_langgraph_update()

    agent = CensusQueryAgent()
    result = agent.solve(user_query=user_question, intent=intent_channel)

    # Get answer_text from agent result
    answer_text = result.answer_text

    # Fallback: If answer_text is missing, empty, or too short, generate it from the census data
    if not answer_text or len(answer_text.strip()) < 20:
        census_data = result.census_data
        data_summary = result.data_summary

        if census_data.success and data_summary:
            logger.info(
                "answer_text is too short, generating rich answer from census data"
            )
            try:
                generated_answer = generate_llm_answer(
                    user_question=user_question,
                    data_summary=data_summary,
                    geo_context=geo_for_llm,
                    intent=intent_channel,
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

    return CensusGraphPatch(
        artifacts=WorkflowArtifactsState(
            census_data=result.census_data,
            variable_labels=result.variable_labels,
            data_summary=result.data_summary,
            reasoning_trace=result.reasoning_trace,
        ),
        final=FinalResponseState(
            answer_text=answer_text,
            charts_needed=result.charts_needed,
            tables_needed=result.tables_needed,
            footnotes=footnotes,
            generated_files=existing_final.generated_files,
        ),
        logs=["agent: completed reasoning with data"],
    ).as_langgraph_update()
