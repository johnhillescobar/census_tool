from typing import Dict, Any

import logging
from src.state.types import CensusState

from langchain_core.runnables import RunnableConfig
from src.utils.text_utils import (
    is_census_question,
    determine_answer_type,
    extract_measures,
    extract_years,
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
    messages = state.messages or []
    if not messages:
        logger.error("No messages found in state")
        return {
            "error": "No messages found in state",
            "logs": ["intent: ERROR - no messages"],
        }

    # Get the last user message (assuming it is the question)
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
    geo_hint = user_text

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
    """Ask clarifying questions when intent is ambiguous"""

    # Get the current intent and context
    intent = state.intent or {}
    messages = state.messages or []

    # Get the user's last question
    user_question = ""
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, dict) and "content" in last_message:
            user_question = last_message["content"]

    # Determine what needs clarification
    clarification_needed = []

    if not intent.get("measures"):
        clarification_needed.append("what specific data you're looking for")

    if not intent.get("time"):
        clarification_needed.append("what time period you're interested in")

    if not state.geo:
        clarification_needed.append("what location you want data for")

    # Build clarification message
    if clarification_needed:
        clarification_text = "I need a bit more information to help you:"
        for i, item in enumerate(clarification_needed, 1):
            clarification_text += f"\n{i}. {item}"
        clarification_text += (
            "\n\nPlease provide more details and I'll find the data for you!"
        )
    else:
        clarification_text = "I'm not sure I understand your question. Could you please rephrase it or provide more details about what Census data you're looking for?"

    response = {
        "type": "clarification",
        "message": clarification_text,
        "user_question": user_question,
        "clarification_needed": clarification_needed,
    }

    return {
        "final": response,
        "logs": [
            f"clarify: asked for clarification on {len(clarification_needed)} items"
        ],
    }
