import os
import sys
import json
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .config import (
    LLM_CONFIG,
    INTENT_PROMPT_TEMPLATE,
    CLARIFICATION_PROMPT_TEMPLATE,
    ANSWER_PROMPT_TEMPLATE,
)

load_dotenv()


logger = logging.getLogger(__name__)


def parse_intent_with_llm(
    user_text: str, user_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """Parse intent using LLM when heuristic parsing has low confidence"""

    # Build context from user text and profile
    profile_context = "No profile available"
    if user_profile:
        profile_context = f"User profile: {user_profile.get('preferences', {})}"

    prompt = INTENT_PROMPT_TEMPLATE.format(
        user_question=user_text,
        user_profile=profile_context,
        recent_queries="No recent queries",  # Could enhance with conversation history
    )

    # Call LLM (you'll need to implement the actual LLM call)
    llm = ChatOpenAI(model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature"])
    llm_response = llm.invoke(prompt)

    # llm_response = {
    #     "is_census": True,  # Assume census for now
    #     "answer_type": "single",  # Default
    #     "measures": ["population"],  # Default
    #     "time": {},
    #     "geo_hint": user_text,
    #     "confidence": 0.8,  # LLM confidence
    #     "method": "llm",
    # }

    llm_response = json.loads(llm_response.content)

    return llm_response


def merge_intent_results(
    heuristic_intent: Dict[str, Any], llm_intent: Dict[str, Any]
) -> Dict[str, Any]:
    """Intelligently merge heuristic and LLM intent results"""
    merged = heuristic_intent.copy()

    # Use LLM results for fields where heuristic had low confidence
    if not heuristic_intent.get("measures") and llm_intent.get("measures"):
        merged["measures"] = llm_intent["measures"]

    if not heuristic_intent.get("time") and llm_intent.get("time"):
        merged["time"] = llm_intent["time"]

    if heuristic_intent.get("geo_hint") == heuristic_intent.get("original_text"):
        # Use LLM geo_hint if available, otherwise keep heuristic
        merged["geo_hint"] = llm_intent.get("geo_hint") or merged["geo_hint"]

    # Ensure geo_hint is never None
    if not merged.get("geo_hint"):
        logger.warning("geo_hint was None, falling back to original text")
        merged["geo_hint"] = heuristic_intent.get("original_text", "")

    # Update confidence and method
    merged["confidence"] = max(
        heuristic_intent.get("confidence", 0), llm_intent.get("confidence", 0)
    )
    merged["method"] = "hybrid"

    return merged


def generate_intelligent_clarification(
    user_question: str,
    clarification_needed: List[str],
    intent: Dict[str, Any],
    available_options: Dict[str, Any] = None,
) -> str:
    """Generate an intelligent clarification question" using LLM"""

    prompt = CLARIFICATION_PROMPT_TEMPLATE.format(
        user_question=user_question,
        available_options=available_options or "No available options",
        user_profile="No profile available",  # TODO review this when you have finished
    )

    llm = ChatOpenAI(model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature"])

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        # Fallback to simple clarification
        logger.error(f"Error generating clarification: {e}")
        return f"I'd be happy to help! Could you clarify: {', '.join(clarification_needed)}?"


def build_data_summary(
    artifacts: Dict[str, Any], geo: Dict[str, Any], intent: Dict[str, Any]
) -> str:
    """Extract key data points for LLM to format naturally"""

    datasets = artifacts.get("datasets", {})
    previews = artifacts.get("previews", {})
    answer_type = intent.get("answer_type", "single")
    measures = intent.get("measures", [])

    if not datasets:
        return "No data available"

    summary_parts = []

    if answer_type == "single":
        # For single value, extract the first value from the first dataset
        for year, preview in previews.items():
            if preview:
                summary_parts.append(f"Year {year}: {preview}")

    elif answer_type == "series":
        # For series, show trend across years
        summary_parts.append("Time Series Data")
        for year in sorted(previews.keys()):
            df = datasets.get(year, {})
            if not df.empty and measures:
                for measure in measures:
                    if measure in df.columns:
                        value = df[measure].iloc[0]
                        summary_parts.append(f"{measure}: in {year}: {value:,}")

    elif answer_type == "table":
        # For table, show high and low values
        summary_parts.append("Table Data -Comparison Data:")
        for year, df in datasets.items():
            # Show multiple rows/comparisons
            if not df.empty:
                # Show multiple rows/comparisons
                summary_parts.append(f"Year {year}:")
                for index, row in df.iterrows():
                    row_summary = ", ".join(
                        [f"{col}: {val}" for col, val in row.items()]
                    )
                    summary_parts.append(row_summary)

    return (
        "\n".join(summary_parts)
        if summary_parts
        else "Data retrieved but no values found"
    )


def generate_llm_answer(
    user_question: str,
    data_summary: str,
    geo_context: Dict[str, Any],
    intent: Dict[str, Any],
) -> str:
    """Generate natural language answer using LLM"""

    # Extract answer_type from intent
    answer_type = intent.get("answer_type", "single")

    # Format geographic context
    geo_level = geo_context.get("level", "Unknown")
    geo_name = geo_context.get("name", "Unknown")
    geo_text = f"{geo_level} level data for {geo_name}"

    # Build prompt with answer_type
    prompt = ANSWER_PROMPT_TEMPLATE.format(
        user_question=user_question,
        answer_type=answer_type,
        data_summary=data_summary,
        geo_context=geo_text,
    )

    llm = ChatOpenAI(
        model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature_text"]
    )

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        return None  # Signal to use template formatting
