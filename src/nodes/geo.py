from typing import Dict, Any
from src.state.types import CensusState

from langchain_core.runnables import RunnableConfig
from src.services.geography_cache import resolve_geography_hint
from src.utils.geo_utils import (
    validate_geography_level,
    get_unsupported_level_message,
)

import logging

logger = logging.getLogger(__name__)


def geo_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Resolve the geography hints into Census API filters"""

    # Get intent and profile from state
    intent = state.intent or {}
    profile = state.profile or {}

    if not intent:
        logger.error("No intent found in state")
        return {
            "error": "No intent found in state",
            "logs": ["geo: ERROR - no intent"],
        }

    # FIX 4: Check if intent already has enumeration info (detected early)
    enumeration = intent.get("enumeration")
    if enumeration and enumeration.get("needs_enumeration"):
        logger.info(
            f"Using enumeration from intent: {enumeration['level']} (confidence: {enumeration['confidence']})"
        )

        # Use enumeration filters directly (already built correctly)
        resolved_geo = {
            "level": enumeration["level"],
            "filters": enumeration["filters"],
            "note": f"Enumeration: {enumeration.get('reason', 'pattern detected')}",
            "confidence": enumeration["confidence"],
            "fips_codes": enumeration.get("parent_geography", {}),
        }

        log_entry = f"geo: using enumeration - {enumeration['level']} (pattern: {enumeration.get('reason', 'N/A')})"
        return {"geo": resolved_geo, "logs": [log_entry]}

    # Get geography hint from intent (for non-enumeration cases)
    geo_hint = intent.get("geo_hint", "")
    profile_default_geo = profile.get("default_geo", {})

    logger.info(f"Resolving geography hint: '{geo_hint}'")

    # Resolve the geography hint
    try:
        resolved_geo = resolve_geography_hint(geo_hint, profile_default_geo)

        # Validate the resolved level
        level = resolved_geo.get("level", "")
        if not validate_geography_level(level):
            logger.error(f"Unsupported geography level: '{level}'")

            # Return error for unsupported levels
            error_message = get_unsupported_level_message(level)
            return {
                "error": error_message,
                "logs": ["geo: ERROR - unsupported geography level"],
            }

        # Create log entry
        filters = resolved_geo.get("filters", {})
        note = resolved_geo.get("note", "")
        log_entry = f"geo: resolved '{geo_hint}' -> {level}:{filters} ({note})"

        logger.info(f"Geography resolution result: {resolved_geo}")

        return {"geo": resolved_geo, "logs": [log_entry]}

    except Exception as e:
        logger.error(f"Error resolving geography hint: {str(e)}")
        return {
            "error": f"Error resolving geography: {str(e)}",
            "logs": [f"geo: ERROR - {str(e)}"],
        }
