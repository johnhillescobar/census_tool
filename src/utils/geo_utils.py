"""
Geography resolution utility functions for the Census app
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Geography mappings from hints to Census API filters
GEOGRAPHY_MAPPINGS = {
    # Place level (city/town)
    "nyc": {
        "level": "place",
        "filters": {"for": "place:51000", "in": "state:36"},
        "note": "New York City",
    },
    "new_york_city": {
        "level": "place",
        "filters": {"for": "place:51000", "in": "state:36"},
        "note": "New York City",
    },
    # State level
    "california": {
        "level": "state",
        "filters": {"for": "state:06"},
        "note": "California",
    },
    "ca": {"level": "state", "filters": {"for": "state:06"}, "note": "California"},
    "texas": {"level": "state", "filters": {"for": "state:48"}, "note": "Texas"},
    "tx": {"level": "state", "filters": {"for": "state:48"}, "note": "Texas"},
    "florida": {"level": "state", "filters": {"for": "state:12"}, "note": "Florida"},
    "fl": {"level": "state", "filters": {"for": "state:12"}, "note": "Florida"},
    "illinois": {"level": "state", "filters": {"for": "state:17"}, "note": "Illinois"},
    "il": {"level": "state", "filters": {"for": "state:17"}, "note": "Illinois"},
    "chicago": {
        "level": "place",
        "filters": {"for": "place:14000", "in": "state:17"},
        "note": "Chicago",
    },
    # Nation level
    "nation": {"level": "nation", "filters": {"for": "us:1"}, "note": "United States"},
    "national": {
        "level": "nation",
        "filters": {"for": "us:1"},
        "note": "United States",
    },
    "usa": {"level": "nation", "filters": {"for": "us:1"}, "note": "United States"},
    "united_states": {
        "level": "nation",
        "filters": {"for": "us:1"},
        "note": "United States",
    },
}

# Default geography (NYC)
DEFAULT_GEO = {
    "level": "place",
    "filters": {"for": "place:51000", "in": "state:36"},
    "note": "New York City (default)",
}


def resolve_geography_hint(
    geo_hint: str, profile_default_geo: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolve geography hint into Census API filters

    Args:
        geo_hint: Geography hint from intent analysis
        profile_default_geo: User's default geography from profile

    Returns:
        Dictionary with level, filters, and note
    """
    # First, try profile default if not specific hint
    if not geo_hint or geo_hint.strip() == "":
        if profile_default_geo and profile_default_geo.get("level"):
            return profile_default_geo
        else:
            logger.info("No default geo found, using default")
            return DEFAULT_GEO

    # Normilize the hint
    hint_lower = geo_hint.lower().strip()

    # Check for unsupported geography levels first
    unsupported_levels = ["tract", "block_group", "block group", "blockgroup"]
    if hint_lower in unsupported_levels:
        # Return the unsupported level so validation can catch it
        return {
            "level": "tract" if hint_lower in ["tract"] else "block_group",
            "filters": {},
            "note": f"Unsupported geography level: {geo_hint}",
        }

    # Check direct mappings
    if hint_lower in GEOGRAPHY_MAPPINGS:
        result = GEOGRAPHY_MAPPINGS[hint_lower].copy()
        logger.info(f"Resolved hint '{geo_hint}' to {result}")
        return result

    # Handle special cases that need more complex resolution
    if "county" in hint_lower or "counties" in hint_lower:
        return {
            "level": "county",
            "filters": {
                "for": "county:*",
                "in": "state:17",
            },  # Default to Illinois for now
            "note": f"County-level request for '{geo_hint}' - needs clarification",
        }

    # Check for state names in the hint
    for state_hint, mapping in GEOGRAPHY_MAPPINGS.items():
        if state_hint.lower() in hint_lower:
            result = mapping.copy()
            result["note"] = (
                f"State-level request for '{geo_hint}' to {mapping['note']}"
            )
            logger.info(f"Resolved hint '{geo_hint}' to {result}")
            return result

    # If we can't resolve the hint, use the default
    logger.info(f"Unable to resolve hint '{geo_hint}', using default")
    result = DEFAULT_GEO.copy()
    result["note"] = f"Default geography: '{DEFAULT_GEO['note']}'"
    return result


def validate_geography_level(level: str) -> bool:
    """Validate if geography level is currently supported"""
    supported_levels = ["place", "state", "county", "nation"]
    return level in supported_levels


def get_unsupported_level_message(level: str) -> str:
    """Get message for unsupported geography level"""
    if level == "tract":
        return (
            "Tract-level geography is not yet supported. "
            "Expected format: for=tract:&in=state:SS&in=county:CCC. "
            "Please try place, county, or state level instead."
        )

    elif level == "block_group":
        return (
            "Block group-level geography is not yet supported. "
            "Expected format: for=block group:&in=state:SS&in=county:CCC&in=tract:TTTTTT. "
            "Please try place, county, or state level instead."
        )
    else:
        return f"Geography level '{level}' is not supported. Please try place, county, or state level instead."
