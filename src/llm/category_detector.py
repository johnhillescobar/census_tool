"""
LLM-based category detection for Census tables
Uses LLM reasoning instead of keyword matching
"""

import os
import sys
import json
import logging
import traceback
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load .env from project root (parent of src/)
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
env_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path=env_path)

from src.llm.config import LLM_CONFIG, CATEGORY_DETECTION_PROMPT_TEMPLATE  # noqa: E402
from src.llm.factory import create_llm  # noqa: E402

logger = logging.getLogger(__name__)


# Pydantic models for Responses API format
class ReasoningResponse(BaseModel):
    """Reasoning step in Responses API format"""

    id: str
    summary: List[Any] = Field(default_factory=list)
    type: str = Field(default="reasoning")


class TextResponse(BaseModel):
    """Text content in Responses API format"""

    type: str = Field(default="text")
    text: str
    annotations: List[Any] = Field(default_factory=list)
    id: Optional[str] = None


class CategoryDetectionResult(BaseModel):
    """Structured output for category detection"""

    preferred_category: Optional[str] = Field(
        None, description="One of: detail, subject, profile, cprofile, spp, or null"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )
    reasoning: str = Field(..., description="Explanation for the category choice")


# Verify API key is loaded
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.warning(f".env file not found at {env_path} or OPENAI_API_KEY not set")
    logger.warning(f"Project root: {project_root}")
    logger.warning(f"Current working directory: {os.getcwd()}")
    logger.warning(f"Looking for .env at: {env_path}")
    logger.warning(f".env file exists: {os.path.exists(env_path)}")
else:
    # Check for common issues
    api_key_clean = api_key.strip()
    if api_key != api_key_clean:
        logger.warning(
            f"API key has whitespace! Original length: {len(api_key)}, Cleaned length: {len(api_key_clean)}"
        )
        # Update environment variable with cleaned version
        os.environ["OPENAI_API_KEY"] = api_key_clean
    logger.info("OPENAI_API_KEY loaded")


def _extract_text_from_responses_api(response_list: List[Dict[str, Any]]) -> str:
    """
    Extract text content from Responses API format using Pydantic models.

    Args:
        response_list: List of response dictionaries from Responses API

    Returns:
        Text content from the 'text' type response item

    Raises:
        ValueError: If no text content can be extracted
    """
    for item in response_list:
        try:
            # Try to parse as TextResponse
            text_response = TextResponse(**item)
            if text_response.text:
                return text_response.text
        except Exception:
            # Not a TextResponse, continue
            continue

    # Fallback: try to find any dict with 'text' field
    for item in response_list:
        if isinstance(item, dict) and "text" in item:
            text = item.get("text", "")
            if text:
                return text

    raise ValueError(
        f"Could not extract text from Responses API format. "
        f"Response items: {[item.get('type', 'unknown') for item in response_list]}"
    )


def _extract_json_from_response(content: str) -> str:
    """
    Extract JSON from LLM response, handling markdown code blocks and extra text.

    Handles:
    - Raw JSON: {"key": "value"}
    - Markdown code blocks: ```json\n{"key": "value"}\n```
    - Text before/after JSON

    Properly matches braces to find the correct closing brace, even if there
    are additional closing braces in text after the JSON object.
    """
    # Ensure content is a string
    if content is None:
        raise ValueError("Response content is None")
    if not isinstance(content, str):
        content = str(content)

    content = content.strip()

    # Try to find JSON object boundaries
    # Look for opening brace
    start_idx = content.find("{")
    if start_idx == -1:
        # No JSON found, return as-is (will fail parsing but gives better error)
        return content

    # Properly match braces by counting them
    # This handles cases where there are additional closing braces after the JSON
    brace_count = 0
    end_idx = -1

    for i in range(start_idx, len(content)):
        if content[i] == "{":
            brace_count += 1
        elif content[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                # Found the matching closing brace
                end_idx = i
                break

    if end_idx == -1 or end_idx < start_idx:
        # No matching closing brace found, return as-is
        return content

    # Extract JSON portion
    json_text = content[start_idx : end_idx + 1]

    # If wrapped in markdown code blocks, strip them
    if json_text.startswith("```"):
        lines = json_text.split("\n")
        # Remove first line if it's ```json or ```
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        json_text = "\n".join(lines)

    return json_text.strip()


def _log_response_debug(frame_locals: Dict[str, Any], label: str) -> None:
    """Log response/json_text/json_dict only if present in frame (avoids NameError in handlers)."""
    if "response" in frame_locals:
        r = frame_locals["response"]
        if hasattr(r, "content"):
            logger.error(f"[{label}] Response content: {getattr(r, 'content', 'N/A')}")
        else:
            logger.error(f"[{label}] Response (no content): {r}")
    else:
        logger.error(f"[{label}] No response (exception before assignment)")
    if "json_text" in frame_locals:
        logger.error(f"[{label}] Extracted JSON text was: {frame_locals['json_text']}")
    if "json_dict" in frame_locals:
        logger.error(f"[{label}] Parsed JSON dict was: {frame_locals['json_dict']}")


def detect_category_with_llm(user_question: str) -> Dict[str, Any]:
    """
    Use LLM to intelligently determine which Census category fits the query

    This is MUCH more flexible than keyword matching because the LLM can:
    - Understand semantic meaning
    - Handle any phrasing or wording
    - Reason about user intent
    - Provide confidence scores

    Args:
        user_query: The user's natural language question

    Returns:
        {
            "preferred_category": "subject" | "profile" | etc. | None,
            "confidence": 0.0-1.0,
            "reasoning": "explanation"
        }

    Examples:
        "Give me an overview" → {"preferred_category": "subject", "confidence": 0.9}
        "Show me a profile" → {"preferred_category": "profile", "confidence": 0.95}
        "Compare across states" → {"preferred_category": "cprofile", "confidence": 0.85}
        "What's the population?" → {"preferred_category": null, "confidence": 0.5}
    """

    try:
        # Build the prompt
        prompt = CATEGORY_DETECTION_PROMPT_TEMPLATE.format(user_question=user_question)

        # Call the LLM
        llm = create_llm(temperature=LLM_CONFIG["temperature"])
        response = llm.invoke(prompt)

        # Ensure response has content attribute
        if not hasattr(response, "content"):
            raise ValueError(
                f"Response object missing 'content' attribute. Response type: {type(response)}, Response: {response}"
            )

        response_content = response.content
        logger.info(f"response.content type: {type(response_content)}")
        logger.info(f"response.content: {response_content}")

        # Handle Responses API format (list of dicts) vs standard format (string)
        if isinstance(response_content, list):
            # Parse Responses API format using Pydantic models
            text_content = _extract_text_from_responses_api(response_content)
            logger.info(
                f"Extracted text from Responses API format: {text_content[:200]}..."
            )
            response_content = text_content

        # Extract and parse JSON response (handles markdown code blocks)
        json_text = _extract_json_from_response(response_content)
        logger.info(f"json_text: {json_text}")

        # Parse and validate with Pydantic
        json_dict = json.loads(json_text)
        result_model = CategoryDetectionResult(**json_dict)
        result = result_model.model_dump()

        logger.info(f"Category detection result: {result}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        _log_response_debug(locals(), "JSONDecodeError")
        return {
            "preferred_category": None,
            "confidence": 0.0,
            "reasoning": f"Error parsing JSON response: {str(e)}",
        }

    except ValidationError as e:
        logger.error(f"Failed to validate category detection result: {e}")
        _log_response_debug(locals(), "ValidationError")
        return {
            "preferred_category": None,
            "confidence": 0.0,
            "reasoning": f"Error validating response structure: {str(e)}",
        }

    except Exception as e:
        logger.error(f"Error detecting category: {type(e).__name__}: {e}")
        _log_response_debug(locals(), "Exception")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "preferred_category": None,
            "confidence": 0.0,
            "reasoning": f"Error detecting category: {str(e)}",
        }


def boost_category_results(
    results: Dict[str, Any],
    preferred_category: Optional[str],
    confidence: float,
    boosts_amount: float = 0.05,
) -> Dict[str, Any]:
    """
    Boost results matching the preferred category

    The boost is scaled by confidence:
    - High confidence (0.9): Full boost
    - Medium confidence (0.6): Partial boost
    - Low confidence (0.3): Minimal boost

    Args:
        results: ChromaDB query results
        preferred_category: Category to boost (or None)
        confidence: LLM confidence in category detection
        boost_amount: Base boost amount (scaled by confidence)

    Returns:
        Results with adjusted distances
    """
    if not preferred_category or confidence < 0.3:
        logger.info("No category boost applied (no preference or low confidence)")
        return results

    # Scale boost by confidence
    actual_boost = boosts_amount * confidence
    logger.info(
        f"Applying boost of {actual_boost:.3f} to category '{preferred_category}' (confidence: {confidence:.2f})"
    )

    # Make a copy
    boosted_results = {
        "ids": [results["ids"][0][:]],
        "distances": [results["distances"][0][:]],
        "metadatas": [results["metadatas"][0][:]],
    }

    boost_count = 0
    for i, metadata in enumerate(results["metadatas"][0]):
        category = metadata.get("category")

        if category == preferred_category:
            original_distance = results["distances"][0][i]
            boosted_results["distances"][0][i] = max(
                0.0, original_distance - actual_boost
            )
            boost_count += 1

            logger.debug(
                f"Boosted {metadata.get('table_code')}: {original_distance:.3f} → {boosted_results['distances'][0][i]:.3f}"
            )

    logger.info(f"Boosted {boost_count} results in category '{preferred_category}'")
    return boosted_results


def rerank_by_distance(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Re-sort results by distance (lower = better)

    Args:
        results: Results with potentially adjusted distances

    Returns:
        Results sorted by distance (with all fields preserved)
    """

    # Combine into tuples - MUST include documents field
    combined = list(
        zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
            results.get("documents", [[]])[0],  # Include documents
        )
    )

    # Sort by distance
    combined.sort(key=lambda x: x[1])

    # Unpack ALL fields including documents
    ids, distances, metadatas, documents = (
        zip(*combined) if combined else ([], [], [], [])
    )

    return {
        "ids": [list(ids)],
        "distances": [list(distances)],
        "metadatas": [list(metadatas)],
        "documents": [list(documents)],  # Return documents field
    }
