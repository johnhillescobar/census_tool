"""
Geography resolution utility functions for the Census app
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def _parse_filter_clause(clause: Optional[str]) -> Dict[str, str]:
    """Convert a space-delimited geography clause into a dictionary."""
    if not clause:
        return {}
    parts = clause.split()
    parsed: Dict[str, str] = {}
    for segment in parts:
        token, _, value = segment.partition(":")
        if token and value:
            parsed[token] = value
    return parsed


def _mapping_entry(level: str, geo_for: str, *, geo_in: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    filters: Dict[str, str] = {"for": geo_for}
    if geo_in:
        filters["in"] = geo_in
    entry = {
        "level": level,
        "filters": filters,
        "geo_for": _parse_filter_clause(geo_for),
        "geo_in": _parse_filter_clause(geo_in),
        "note": note or "",
    }
    return entry


# Geography mappings from hints to Census API filters
GEOGRAPHY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Place level (city/town)
    "nyc": _mapping_entry("place", "place:51000", geo_in="state:36", note="New York City"),
    "new_york_city": _mapping_entry("place", "place:51000", geo_in="state:36", note="New York City"),
    # State level
    "california": _mapping_entry("state", "state:06", note="California"),
    "ca": _mapping_entry("state", "state:06", note="California"),
    "texas": _mapping_entry("state", "state:48", note="Texas"),
    "tx": _mapping_entry("state", "state:48", note="Texas"),
    "florida": _mapping_entry("state", "state:12", note="Florida"),
    "fl": _mapping_entry("state", "state:12", note="Florida"),
    "illinois": _mapping_entry("state", "state:17", note="Illinois"),
    "il": _mapping_entry("state", "state:17", note="Illinois"),
    "chicago": _mapping_entry("place", "place:14000", geo_in="state:17", note="Chicago"),
    # Nation level
    "nation": _mapping_entry("nation", "us:1", note="United States"),
    "national": _mapping_entry("nation", "us:1", note="United States"),
    "usa": _mapping_entry("nation", "us:1", note="United States"),
    "united_states": _mapping_entry("nation", "us:1", note="United States"),
}

# Default geography (NYC)
DEFAULT_GEO: Dict[str, Any] = _mapping_entry(
    "place",
    "place:51000",
    geo_in="state:36",
    note="New York City (default)",
)


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
            result = profile_default_geo.copy()
            if "geo_for" not in result and "filters" in result:
                result["geo_for"] = _parse_filter_clause(result["filters"].get("for"))
                result["geo_in"] = _parse_filter_clause(result["filters"].get("in"))
            return result
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
        entry = _mapping_entry(
            "county",
            "county:*",
            geo_in="state:17",
            note=f"County-level request for '{geo_hint}' - needs clarification",
        )
        return entry

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
