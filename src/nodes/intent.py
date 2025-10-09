import os
import sys
from typing import Dict, Any

import logging
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import CensusState
from src.utils.text_utils import (
    is_census_question,
    determine_answer_type,
    extract_measures,
    extract_years,
)
from src.llm.intent_enhancer import (
    parse_intent_with_llm,
    merge_intent_results,
    generate_intelligent_clarification,
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


def calculate_heuristic_intent(intent: Dict[str, Any], user_text: str) -> float:
    """Calculate the heuristic intent confidence score"""
    confidence = 1.0

    # Reduce confidence scores if no measures are found
    if not intent.get("measures"):
        confidence -= 0.4

    # Reduce confidence if not time is found
    if not intent.get("time"):
        confidence -= 0.2

    # Reduce confidence if not geo_hint is just the raw_text
    if intent.get("geo_hint") == user_text:
        confidence -= 0.2

    # Reduce confidence if answer_type is not clear
    if intent.get("answer_type") not in ["single", "series", "table"]:
        confidence -= 0.3

    return max(0.0, confidence)


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
    heuristic_intent = {
        "is_census": is_census,
        "answer_type": answer_type,
        "measures": measures,
        "time": time_info,
        "geo_hint": geo_hint,
        "needs_clarification": False,
        "original_text": user_text,
    }

    # Calculate confidence and add method tracking
    confidence = calculate_heuristic_intent(heuristic_intent, user_text)
    heuristic_intent["confidence"] = confidence
    heuristic_intent["method"] = "heuristic"

    # Determine if clarification is needed
    heuristic_intent["needs_clarification"] = needs_clarification(heuristic_intent)

    # Hybrid decision: Use LLM if confidence is low or needs clarification
    if confidence < 0.7 or heuristic_intent.get("needs_clarification"):
        llm_intent = parse_intent_with_llm(user_text, state.profile)
        intent = merge_intent_results(heuristic_intent, llm_intent)
    else:
        intent = heuristic_intent

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
    clarification_text = generate_intelligent_clarification(
        user_question=user_question,
        clarification_needed=clarification_needed,
        intent=intent,
        available_options=state.candidates,  # Use available data options
    )

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
