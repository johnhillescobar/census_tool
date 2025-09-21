from typing import Dict, Any
import logging
from src.state.types import CensusState

logger = logging.getLogger(__name__)


def summarizer_node(state: CensusState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize long conversations to manage context length"""

    messages = state.get("messages", [])
    history = state.get("history", [])

    if not messages:
        return {"summary": None, "logs": ["summarizer: no messages to summarize"]}

    try:
        # Create a summary of the conversation
        summary = _create_conversation_summary(messages, history)

        # Trim messages to keep only recent ones
        trimmed_messages = messages[-8:] if len(messages) > 8 else messages

        return {
            "summary": summary,
            "messages": trimmed_messages,
            "logs": [
                f"summarizer: created summary, trimmed to {len(trimmed_messages)} messages"
            ],
        }

    except Exception as e:
        logger.error(f"Error creating summary: {str(e)}")
        return {"summary": None, "logs": [f"summarizer: ERROR - {str(e)}"]}


def _create_conversation_summary(messages: list, history: list) -> str:
    """Create a summary of the conversation"""

    # Count different types of interactions
    user_questions = 0
    census_questions = 0
    successful_queries = 0

    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_questions += 1

    for hist_item in history:
        if hist_item.get("success"):
            successful_queries += 1
        if hist_item.get("intent", {}).get("measures"):
            census_questions += 1

    # Create summary
    summary_parts = []

    if user_questions > 0:
        summary_parts.append(f"User has asked {user_questions} questions")

    if census_questions > 0:
        summary_parts.append(f"{census_questions} Census-related queries")

    if successful_queries > 0:
        summary_parts.append(f"{successful_queries} successful data retrievals")

    if not summary_parts:
        summary_parts.append("New conversation started")

    return " | ".join(summary_parts)
