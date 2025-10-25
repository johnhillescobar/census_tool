"""
Enumeration Detection for Census Queries

Detects when a query needs multiple geographic areas (enumeration)
vs. a single specific area.

Examples:
- "Compare counties in California" → needs enumeration (for=county:*&in=state:06)
- "Population of New York City" → single area (for=place:51000&in=state:36)
"""

import logging
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EnumerationRequest:
    """Structured representation of an enumeration request"""

    needs_enumeration: bool
    summary_level: str  # "county", "place", "tract", etc.
    parent_geography: Optional[Dict[str, str]] = None  # e.g., {"state": "06"}
    confidence: float = 0.0
    reason: str = ""


class EnumerationDetector:
    """Detect when queries need geographic area enumeration"""

    # Keywords that indicate enumeration requests
    ENUMERATION_KEYWORDS = [
        r"all\s+(?:the\s+)?(\w+)\s+in",  # "all counties in"
        r"each\s+(\w+)\s+in",  # "each county in"
        r"every\s+(\w+)\s+in",  # "every place in"
        r"compare\s+(\w+)\s+in",  # "compare counties in"
        r"list\s+(?:of\s+)?(\w+)\s+in",  # "list of cities in"
        r"show\s+(?:me\s+)?(\w+)\s+in",  # "show me places in"
        r"by\s+(\w+)\s+in",  # "by county in"
        r"(\w+)\s+by\s+(\w+)",  # "population by county"
    ]

    # Geography level mappings
    GEOGRAPHY_LEVEL_MAP = {
        "county": "county",
        "counties": "county",
        "city": "place",
        "cities": "place",
        "town": "place",
        "towns": "place",
        "place": "place",
        "places": "place",
        "tract": "tract",
        "tracts": "tract",
        "census tract": "tract",
        "census tracts": "tract",
        "zip": "zip code tabulation area",
        "zip code": "zip code tabulation area",
        "zcta": "zip code tabulation area",
        "school district": "school district (unified)",
        "school districts": "school district (unified)",
    }

    # State name to FIPS mapping (partial - add more as needed)
    STATE_FIPS = {
        "california": "06",
        "ca": "06",
        "texas": "48",
        "tx": "48",
        "florida": "12",
        "fl": "12",
        "new york": "36",
        "ny": "36",
        "illinois": "17",
        "il": "17",
        "pennsylvania": "42",
        "pa": "42",
        "ohio": "39",
        "oh": "39",
        "georgia": "13",
        "ga": "13",
        "michigan": "26",
        "mi": "26",
        "north carolina": "37",
        "nc": "37",
    }

    def __init__(self):
        self.patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.ENUMERATION_KEYWORDS
        ]

    def detect(self, query: str, intent: Dict[str, Any] = None) -> EnumerationRequest:
        """
        Detect if query needs enumeration

        Args:
            query: User's query text
            intent: Optional intent dictionary from intent_node

        Returns:
            EnumerationRequest with detection results
        """
        query_lower = query.lower()

        # Check each enumeration pattern
        for pattern in self.patterns:
            match = pattern.search(query_lower)
            if match:
                # Extract the geography level mentioned
                geography_level = match.group(1) if match.lastindex >= 1 else None

                if geography_level:
                    # Normalize the geography level
                    normalized_level = self._normalize_geography_level(geography_level)

                    # Extract parent geography (e.g., "in California")
                    parent_geo = self._extract_parent_geography(query_lower)

                    if normalized_level:
                        logger.info(
                            f"Enumeration detected: {normalized_level} in {parent_geo}"
                        )
                        return EnumerationRequest(
                            needs_enumeration=True,
                            summary_level=normalized_level,
                            parent_geography=parent_geo,
                            confidence=0.9,
                            reason=f"Matched pattern: {pattern.pattern}",
                        )

        # No enumeration detected
        return EnumerationRequest(
            needs_enumeration=False,
            summary_level="",
            parent_geography=None,
            confidence=1.0,
            reason="No enumeration keywords found",
        )

    def _normalize_geography_level(self, level: str) -> Optional[str]:
        """Normalize geography level name to Census API format"""
        level_lower = level.lower().strip()
        return self.GEOGRAPHY_LEVEL_MAP.get(level_lower)

    def _extract_parent_geography(self, query: str) -> Optional[Dict[str, str]]:
        """
        Extract parent geography from query

        Examples:
        - "counties in California" → {"state": "06"}
        - "cities in Texas" → {"state": "48"}
        """
        # Look for "in [State Name]" pattern
        in_pattern = re.compile(r"\s+in\s+([a-z\s]+?)(?:\s|$|,|\?)", re.IGNORECASE)
        match = in_pattern.search(query)

        if match:
            location_name = match.group(1).strip().lower()

            # Check if it's a state
            state_fips = self.STATE_FIPS.get(location_name)
            if state_fips:
                return {"state": state_fips}

            # Could be a longer state name - try partial matching
            for state_name, fips in self.STATE_FIPS.items():
                if state_name in location_name or location_name in state_name:
                    return {"state": fips}

        return None

    def build_enumeration_filters(self, request: EnumerationRequest) -> Dict[str, str]:
        """
        Build Census API filters for enumeration

        Args:
            request: EnumerationRequest from detect()

        Returns:
            Dictionary with 'for' and optionally 'in' keys

        Examples:
        - {"for": "county:*", "in": "state:06"}
        - {"for": "place:*", "in": "state:48"}
        """
        if not request.needs_enumeration:
            return {}

        filters = {"for": f"{request.summary_level}:*"}

        if request.parent_geography:
            # Build 'in' clause from parent geography
            # Format: "state:06" (the "in=" will be added by build_census_url)
            in_parts = []
            for geo_type, geo_code in request.parent_geography.items():
                in_parts.append(f"{geo_type}:{geo_code}")

            if in_parts:
                # Join multiple levels with &in= between them
                filters["in"] = "&in=".join(in_parts)

        return filters


def detect_and_build_enumeration(
    query: str, intent: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function: Detect enumeration and build filters

    Returns:
        Dictionary with enumeration info if detected, None otherwise
        {
            "needs_enumeration": True,
            "level": "county",
            "filters": {"for": "county:*", "in": "state:06"},
            "confidence": 0.9
        }
    """
    detector = EnumerationDetector()
    request = detector.detect(query, intent)

    if not request.needs_enumeration:
        return None

    filters = detector.build_enumeration_filters(request)

    return {
        "needs_enumeration": True,
        "level": request.summary_level,
        "filters": filters,
        "parent_geography": request.parent_geography,
        "confidence": request.confidence,
        "reason": request.reason,
    }


if __name__ == "__main__":
    # Test the detector
    detector = EnumerationDetector()

    test_queries = [
        "What's the population of New York City?",  # NOT enumeration
        "Compare population by county in California",  # IS enumeration
        "Show me all counties in Texas",  # IS enumeration
        "List cities in Florida",  # IS enumeration
        "Population by county in New York",  # IS enumeration
        "Median income for Chicago",  # NOT enumeration
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        result = detector.detect(query)
        print(f"Needs enumeration: {result.needs_enumeration}")
        print(f"Summary level: {result.summary_level}")
        print(f"Parent geography: {result.parent_geography}")
        print(f"Confidence: {result.confidence}")

        if result.needs_enumeration:
            filters = detector.build_enumeration_filters(result)
            print(f"Filters: {filters}")
