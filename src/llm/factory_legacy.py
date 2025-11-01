"""
Legacy LLM creation - fallback if factory fails
Preserves original ChatOpenAI behavior for rollback safety
"""

import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langchain_openai import ChatOpenAI
from src.llm.config import LLM_CONFIG


def create_legacy_openai_llm(temperature: Optional[float] = None) -> ChatOpenAI:
    """
    Original ChatOpenAI creation logic (pre-factory)

    This function preserves the original behavior for rollback purposes.
    To rollback to legacy behavior, set ENABLE_FACTORY = False in factory.py

    Args:
        temperature: Override config temperature (optional)

    Returns:
        ChatOpenAI instance with original configuration
    """
    temp = temperature if temperature is not None else LLM_CONFIG["temperature"]

    return ChatOpenAI(
        model=LLM_CONFIG["model"],
        temperature=temp,
        max_tokens=LLM_CONFIG.get("max_tokens", 500),
        timeout=LLM_CONFIG.get("timeout", 30),
    )
