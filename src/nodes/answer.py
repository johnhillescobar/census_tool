from typing import Dict, Any
import pandas as pd
import logging
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from src.state.types import CensusState
from src.utils.text_utils import (
    format_single_value_answer,
    format_series_answer,
    format_table_answer,
    generate_footnotes,
)

logger = logging.getLogger(__name__)


def answer_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Format the final answer based on intent and artifacts

    Requirements:
    1. Load datasets from artifacts.datasets
    2. For single values: format with thousands separators, include year/dataset/geo
    3. For series/table: create consolidated table, save to data/, show preview
    4. Generate footnotes with variable codes and dataset info
    5. Handle missing data gracefully
    """

    # Get state components
    intent = state.intent or {}
    geo = state.geo or {}
    artifacts = state.artifacts or {}
    datasets = artifacts.get("datasets", {})
    previews = artifacts.get("previews", {})

    if not datasets:
        return {
            "error": "No datasets found to answer question",
            "logs": ["answer: ERROR - no datasets available"],
        }

    # Determine answer type from intent
    answer_type = intent.get("answer_type", "single")
    measure = intent.get("measures", [])
    time_info = intent.get("time", {})

    try:
        if answer_type == "single":
            result = format_single_value_answer(datasets, previews, geo, intent)
        elif answer_type == "series":
            result = format_series_answer(datasets, previews, geo, intent)
        elif answer_type == "table":
            result = format_table_answer(datasets, previews, geo, intent)
        else:
            result = format_single_value_answer(datasets, previews, geo, intent)

        # Add footnotes
        footnotes = generate_footnotes(datasets, geo, intent)
        result["footnotes"] = footnotes

        return {
            "final": result,
            "logs": [
                f"answer: formatted {answer_type} answer with {len(datasets)} datasets"
            ],
        }

    except Exception as e:
        logger.error(f"Error formatting answer: {str(e)}")
        return {
            "error": f"Error formatting answer: {str(e)}",
            "logs": [f"answer: ERROR - {str(e)}"],
        }


def not_census_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Return a message indicating the question is not related to Census"""

    # Get the user's question from messages
    messages = state.messages or []
    user_question = ""

    if messages:
        last_message = messages[-1]
        if isinstance(last_message, dict) and "content" in last_message:
            user_question = last_message["content"]

    response = {
        "type": "not census",
        "message": "I'm a Census data assistant. I can help you find population, demographic, economic, and housing data from the U.S. Census Bureau.",
        "suggestion": "Try asking about population, income, demographics, or housing in specific locations.",
        "user_question": user_question,
    }

    return {"final": response, "logs": "not census: provided non-Census response"}
