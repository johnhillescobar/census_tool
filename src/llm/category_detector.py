"""
LLM-based category detection for Census tables
Uses LLM reasoning instead of keyword matching
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.llm.config import LLM_CONFIG, CATEGORY_DETECTION_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

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
        llm = ChatOpenAI(model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature"])
        response = llm.invoke(prompt)

        # Parse JSON response
        result = json.loads(response.content)

        logger.info(f"Category detection result: {result}")
        return result
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response was: {response.content}")
        return {
            "preferred_category": None,
            "confidence": 0.0,
            "reasoning": f"Error parsing JSON response: {str(e)}",
        }

    except Exception as e:
        logger.error(f"Error detecting category: {e}")
        return {
            "preferred_category": None,
            "confidence": 0.0,
            "reasoning": f"Error detecting category: {str(e)}",
        }
        

def boost_category_results(
    results: Dict[str, Any], 
    preferred_category: Optional[str], 
    confidence: float, 
    boosts_amount: float = 0.05
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
    logger.info(f"Applying boost of {actual_boost:.3f} to category '{preferred_category}' (confidence: {confidence:.2f})")

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
            boosted_results["distances"][0][i] = max(0.0, original_distance - actual_boost)
            boost_count += 1

            logger.debug(f"Boosted {metadata.get('table_code')}: {original_distance:.3f} → {boosted_results['distances'][0][i]:.3f}")
    
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
    combined = list(zip(
        results["ids"][0], 
        results["distances"][0], 
        results["metadatas"][0],
        results.get("documents", [[]])[0]  # Include documents
    ))
    
    # Sort by distance
    combined.sort(key=lambda x: x[1])
    
    # Unpack ALL fields including documents
    ids, distances, metadatas, documents = zip(*combined) if combined else ([], [], [], [])
    
    return {
        'ids': [list(ids)],
        'distances': [list(distances)],
        'metadatas': [list(metadatas)],
        'documents': [list(documents)]  # Return documents field
    }

