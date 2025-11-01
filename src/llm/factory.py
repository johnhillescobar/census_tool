"""
Centralized LLM factory supporting multiple providers
Handles provider-specific initialization and API compatibility
"""

import os
import sys
import logging
from typing import Any, Optional
from langchain_openai import ChatOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.llm.config import LLM_CONFIG

logger = logging.getLogger(__name__)

# Feature flag for easy rollback to legacy behavior
ENABLE_FACTORY = True


def create_llm(temperature: Optional[float] = None, **kwargs) -> Any:
    """
    Central LLM factory supporting OpenAI, Anthropic, and Google Gemini

    Args:
        temperature: Override config temperature (optional)
        **kwargs: Additional provider-specific parameters

    Returns:
        Configured LLM instance with provider-specific handling

    Raises:
        ValueError: If provider is not supported
    """
    if not ENABLE_FACTORY:
        from src.llm.factory_legacy import create_legacy_openai_llm

        return create_legacy_openai_llm(temperature)

    provider = LLM_CONFIG.get("provider", "openai").lower()
    model = LLM_CONFIG["model"]
    temp = temperature if temperature is not None else LLM_CONFIG["temperature"]

    logger.info(f"Creating LLM: provider={provider}, model={model}, temperature={temp}")

    if provider == "openai":
        return _create_openai_llm(model, temp, **kwargs)
    elif provider == "anthropic":
        return _create_anthropic_llm(model, temp, **kwargs)
    elif provider == "google":
        return _create_gemini_llm(model, temp, **kwargs)
    else:
        raise ValueError(
            f"Unsupported provider: {provider}. Supported: openai, anthropic, google"
        )


def _create_openai_llm(model: str, temperature: float, **kwargs) -> Any:
    """
    Create OpenAI LLM with automatic API compatibility handling

    Args:
        model: OpenAI model name
        temperature: Temperature setting
        **kwargs: Additional OpenAI-specific parameters

    Returns:
        ChatOpenAI instance with appropriate API binding
    """

    # GPT-5+ compatibility: Set output_version for Responses API
    # Models >= GPT-5 require Responses API with specific output version
    # Models <= GPT-4.1 use Chat Completions API (work as usual)
    if _is_gpt5_or_higher(model):
        # Add output_version for Responses API compatibility
        if "output_version" not in kwargs:
            kwargs["output_version"] = "responses/v1"
        logger.info(
            f"Using Responses API for {model} with output_version={kwargs['output_version']}"
        )

    # Create base LLM instance
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=LLM_CONFIG.get("max_tokens", 500),
        timeout=LLM_CONFIG.get("timeout", 30),
        **kwargs,
    )

    # GPT-5+ compatibility: Wrap LLM to filter 'stop' parameter for Responses API
    if _is_gpt5_or_higher(model):
        llm = _wrap_llm_for_responses_api(llm, model)
        logger.info(f"Applied stop parameter filtering for {model}")
    else:
        logger.info(f"Using standard Chat Completions API for {model}")

    return llm


def _wrap_llm_for_responses_api(llm: Any, model: str) -> Any:
    """
    Wrap LLM to filter out 'stop' parameter at invocation time

    This is necessary because:
    1. AgentExecutor passes stop sequences at runtime
    2. LangChain's _construct_responses_api_payload doesn't filter 'stop'
    3. We need to intercept at _get_request_payload level before API call

    Args:
        llm: The ChatOpenAI instance
        model: Model name for logging

    Returns:
        Wrapped LLM that filters stop parameters from the request payload
    """
    # Monkey-patch _get_request_payload to filter stop before it reaches the API
    original_get_request_payload = llm._get_request_payload

    def filtered_get_request_payload(input_, *, stop=None, **kwargs):
        # Always set stop to None for GPT-5+ models
        if stop is not None:
            logger.debug(f"Filtering out stop sequences for {model}: {stop}")
            stop = None

        # Call original method with filtered stop
        payload = original_get_request_payload(input_, stop=stop, **kwargs)

        # Extra safety: remove 'stop' from payload if it somehow got through
        if "stop" in payload:
            logger.debug(f"Removing 'stop' from payload for {model}")
            payload.pop("stop")

        return payload

    # Apply the monkey patch
    llm._get_request_payload = filtered_get_request_payload

    return llm


def _is_gpt5_or_higher(model: str) -> bool:
    """
    Detect GPT-5+ family models that require Responses API

    Returns True ONLY for:
    - gpt-5, gpt-5-mini, gpt-5-turbo, etc. (any variant with "gpt-5")
    - o1, o1-preview, o1-mini (reasoning models)
    - o3, o3-mini (future reasoning models)

    Returns False for (Chat Completions - work as usual):
    - gpt-4.1, gpt-4o, gpt-4o-mini, gpt-4-turbo
    - gpt-4, gpt-4-32k
    - gpt-3.5-turbo

    Args:
        model: Model name string

    Returns:
        True if model requires Responses API, False otherwise
    """
    model_lower = model.lower()

    # GPT-5 family (all variants) - Responses API
    if "gpt-5" in model_lower:
        return True

    # O-series reasoning models (o1, o3) - Responses API
    if model_lower.startswith("o1") or model_lower.startswith("o3"):
        return True

    # Everything else uses Chat Completions (including gpt-4.1, gpt-4o, etc.)
    # NO binding applied - work as usual
    return False


def _create_anthropic_llm(model: str, temperature: float, **kwargs) -> Any:
    """
    Create Anthropic Claude LLM

    Args:
        model: Anthropic model name (e.g., claude-3-5-sonnet-20241022)
        temperature: Temperature setting
        **kwargs: Additional Anthropic-specific parameters

    Returns:
        ChatAnthropic instance
    """
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        logger.error(
            "langchain-anthropic not installed. Run: uv add langchain-anthropic"
        )
        raise

    return ChatAnthropic(
        model=model,
        temperature=temperature,
        max_tokens=LLM_CONFIG.get("max_tokens", 500),
        timeout=LLM_CONFIG.get("timeout", 30),
        **kwargs,
    )


def _create_gemini_llm(model: str, temperature: float, **kwargs) -> Any:
    """
    Create Google Gemini LLM

    Args:
        model: Gemini model name (e.g., gemini-1.5-pro)
        temperature: Temperature setting
        **kwargs: Additional Gemini-specific parameters

    Returns:
        ChatGoogleGenerativeAI instance
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        logger.error(
            "langchain-google-genai not installed. Run: uv add langchain-google-genai"
        )
        raise

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_output_tokens=LLM_CONFIG.get("max_tokens", 500),
        timeout=LLM_CONFIG.get("timeout", 30),
        streaming=False,  # Disable streaming to prevent "No generation chunks" error
        **kwargs,
    )


def create_llm_with_fallback(temperature: Optional[float] = None, **kwargs) -> Any:
    """
    Create LLM with automatic fallback on failure

    Attempts to create LLM with primary model. On failure, falls back
    to fallback_model if configured.

    Args:
        temperature: Override config temperature (optional)
        **kwargs: Additional provider-specific parameters

    Returns:
        Configured LLM instance

    Raises:
        Exception: If both primary and fallback creation fail
    """
    try:
        return create_llm(temperature=temperature, **kwargs)
    except Exception as e:
        logger.error(f"Primary LLM creation failed: {e}")
        fallback_model = LLM_CONFIG.get("fallback_model")

        if fallback_model:
            logger.info(f"Attempting fallback to {fallback_model}")
            # Temporarily override config
            original_model = LLM_CONFIG["model"]
            LLM_CONFIG["model"] = fallback_model

            try:
                llm = create_llm(temperature=temperature, **kwargs)
                logger.info(f"Successfully created fallback LLM: {fallback_model}")
                return llm
            except Exception as fallback_error:
                logger.error(f"Fallback LLM creation also failed: {fallback_error}")
                raise
            finally:
                # Restore original model
                LLM_CONFIG["model"] = original_model
        else:
            logger.error("No fallback model configured")
            raise
