from typing import Dict, Any

import logging
from src.state.types import CensusState

from langchain_core.runnables import RunnableConfig
from src.utils.text_utils import (
    is_census_question,
    determine_answer_type,
    extract_measures,
    extract_years,
    extract_geo_hint,
)

logger = logging.getLogger(__name__)


def needs_clarification(intent: Dict[str, Any]) -> bool:
    """Determine if question needs clarification"""
    if not intent.get("measures"):
        return True

    if not intent.get("geo_hint") or intent.get("geo_hint") == "":
        return True

    # Check for conflicting signals
    measures = intent.get("measures", [])
    if len(measures) > 2:
        return True

    return False


def intent_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Parse user intent heuristically"""

    # Get the latest user message
    messages = state.get("messages", [])
    if not messages:
        logger.error("No messages found in state")
        return {
            "error": "No messages found in state",
            "logs": ["intent: ERROR - no messages"],
        }

    # Get the last under message (assuming it is the question)
    last_message = messages[-1]
    if last_message.get("role") != "user":
        logger.error("Last message is not a user message")
        return {
            "error": "Last message is not a user message",
            "logs": ["intent: ERROR - last message is not a user message"],
        }

    user_text = last_message.get("content", "")
    if not user_text:
        logger.error("Empty user message")
        return {
            "error": "Empty user message",
            "logs": ["intent: ERROR - empty message"],
        }

    logger.info(f"Analyzing for: '{user_text}'")

    # Parse intent components
    is_census = is_census_question(user_text)
    answer_type = determine_answer_type(user_text)
    measures = extract_measures(user_text)
    time_info = extract_years(user_text)
    geo_hint = extract_geo_hint(user_text)

    # Build intent object
    intent = {
        "is_census": is_census,
        "answer_type": answer_type,
        "measures": measures,
        "time": time_info,
        "geo_hint": geo_hint,
        "needs_clarification": False,
    }

    # Determine if clarification is needed
    intent["needs_clarification"] = needs_clarification(intent)

    # Create log message
    log_entry = f"intent: analyzed '{user_text[:50]}...' -> census:{is_census}, type:{answer_type}, measures:{measures}, needs_clarify:{intent['needs_clarification']}"

    logger.info(f"Intent analysis result: {intent}")

    return {"intent": intent, "logs": [log_entry]}


def router_from_intent_node(
    state: CensusState, config: RunnableConfig
) -> Dict[str, Any]:
    # This node just passes through - routing is handled by the graph edges
    return {"logs": ["router_from_intent: routing handled by graph edges"]}


def clarify_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Ask clarifying questions"""

    intent = state.get("intent", {})
    messages = state.get("messages", [])

    if not messages:
        return {
            "error": "No messages found for clarification",
            "logs": ["clarify: ERROR - no messages"],
        }

    last_message = messages[-1]
    user_text = last_message.get("content", "")

    # Build clarification questions based on missing information
    questions = []

    if not intent.get("measures"):
        questions.append(
            "What specific measure are you interested in? (e.g., population, median income, unemployment)"
        )

    if not intent.get("geo_hint") or intent.get("geo_hint") == "":
        questions.append(
            "Which geography level do you prefer? (e.g., place, county, tract)"
        )

    if not intent.get("time"):
        questions.append("What year are you interested in? (e.g., 2023, 2012-2023)")

    # Create clarification message
    if questions:
        clarification_text = "I need a bit more information to help you:\n" + "\n".join(
            f"- {q}" for q in questions
        )
    else:
        clarification_text = (
            "Could you please rephrase your question with more specific details?"
        )

    # Add assistant message to conversation
    new_message = {"role": "assistant", "content": clarification_text}

    log_entry = f"clarify: asked {len(questions)} clarifying questions for '{user_text[:30]}...'"

    return {
        "messages": [new_message],
        "final": {"answer_text": clarification_text},
        "logs": [log_entry],
    }
