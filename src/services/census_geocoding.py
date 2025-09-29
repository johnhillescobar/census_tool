import os
import sys
import logging
import requests
import pandas as pd
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from functools import lru_cache
from config import (
    CENSUS_GEOCODING_GEOGRAPHY_URL,
    GEOCODING_TIMEOUT,
    MAX_GEOCODING_RETRIES,
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import ResolvedGeography
from config import SUPPORTED_GEOGRAPHY_LEVELS

logger = logging.getLogger(__name__)


class CensusGeocodingService:
    """Enhanced Census Geocoding Service using both geocoding and data APIs"""

    def __init__(self):
        self.geocoding_url = CENSUS_GEOCODING_GEOGRAPHY_URL
        self.data_api_url = "https://api.census.gov/data/2020/dec/pl"
        self.timeout = GEOCODING_TIMEOUT
        self.max_retries = MAX_GEOCODING_RETRIES
        self.state_data = self._load_state_data()
        self.supported_geography_levels = SUPPORTED_GEOGRAPHY_LEVELS

    def _load_state_data(self) -> Dict[str, str]:
        """Load state data abbrevations from CSV"""
        try:
            csv_path = Path(__file__).parent.parent / "locations" / "states_abbrev.csv"
            df = pd.read_csv(csv_path)

            # Create bidirectional mapping
            state_map = {}

            for _, row in df.iterrows():
                abbrev = row["abbreviation"].upper()
                full_name = row["full_name"]
                state_map[abbrev] = full_name
                state_map[full_name.upper()] = abbrev

            return state_map

        except Exception as e:
            logger.error(f"Error loading state data: {e}")
            return {}

    def _resolve_state_from_csv(self, state: str) -> Optional[str]:
        """Resolve state abbreviation from state name"""
        if not self.state_data:
            return None

        state_upper = state.upper().strip()

        if state_upper in self.state_data:
            return self.state_data[state_upper]

        # Fuzzy match for full names
        for key, full_name in self.state_data.items():
            if len(key) > 2:
                if state_upper in key or key.startswith(state_upper):
                    return full_name

        return None

    def _get_fips_for_state_name(self, state_name: str) -> Optional[str]:
        """Get FIPS code for a resolved state name using Census API"""
        try:
            params = {"get": "NAME", "for": "state:*"}
            response = requests.get(
                self.data_api_url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            state_name_lower = state_name.lower().strip()

            for row in data[1:]:  # Skip header
                name, state_fips = row
                if name.lower().strip() == state_name_lower:
                    return state_fips

            return None

        except Exception as e:
            logger.error(f"Failed to get FIPS for state name '{state_name}': {e}")
            return None

    def _resolve_state_from_api(self, state: str) -> Optional[str]:
        """Fallback: resolve state using Census API when CSV fails"""
        try:
            params = {"get": "NAME", "for": "state:*"}
            response = requests.get(
                self.data_api_url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            state_lower = state.lower().strip()

            # Try exact match first
            for row in data[1:]:  # Skip header
                name, state_fips = row
                if name.lower().strip() == state_lower:
                    return state_fips

            # Try partial match for abbreviations
            for row in data[1:]:
                name, state_fips = row
                # Check if state input matches common abbreviations
                if len(state_lower) == 2:
                    # This is likely an abbreviation - would need abbreviation lookup
                    # For now, return None to avoid incorrect matches
                    continue
                if state_lower in name.lower():
                    return state_fips

            return None

        except Exception as e:
            logger.error(f"Failed to resolve state via API '{state}': {e}")
            return None

    @lru_cache(maxsize=128)
    def _get_state_fips(self, state: str) -> Optional[str]:
        """Get state FIPS code from state name/abbreviation with caching"""
        try:
            # Step 1: Resolve state name using CSV
            resolved_state_name = self._resolve_state_from_csv(state)

            # Step 2: Get FIPS for the resolved name
            if resolved_state_name:
                return self._get_fips_for_state_name(resolved_state_name)

            # Step 3: Fallback to API
            if resolved_state_name:
                return self._get_fips_for_state_name(state)  # Use original full name

            return None

        except Exception as e:
            logger.warning(f"Failed to get state FIPS for '{state}': {e}")
            return None

    @lru_cache(maxsize=256)
    def _get_places_for_state_cached(self, state_fips: str) -> List:
        """Cache place data by state to avoid repeated API calls"""
        try:
            params = {
                "get": "NAME,GEO_ID",
                "for": "place:*",
                "in": f"state:{state_fips}",
            }
            response = requests.get(
                self.data_api_url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data[1:]

        except Exception as e:
            logger.error(f"Failed to get places for state '{state_fips}': {e}")
            return []

    @lru_cache(maxsize=256)
    def _get_counties_for_state_cached(self, state_fips: str) -> list:
        """Cache county data by state"""
        try:
            params = {
                "get": "NAME,GEO_ID",
                "for": "county:*",
                "in": f"state:{state_fips}",
            }

            response = requests.get(
                self.data_api_url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get counties for state '{state_fips}': {e}")
            return []

    def _try_geocoding_api(
        self, place_name: str, state: str = None
    ) -> Optional[ResolvedGeography]:
        """Try the official Census geocoding API first"""
        try:
            # Construct address string
            address = place_name
            if state:
                address += f", {state}"

            params = {
                "address": address,
                "benchmark": "Public_AR_Current",
                "format": "json",
            }

            url = f"{self.geocoding_url}/locations/onelineaddress"
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            # Check if we got a match
            if (
                data.get("result", {}).get("addressMatches")
                and len(data["result"]["addressMatches"]) > 0
            ):
                match = data["result"]["addressMatches"][0]
                coords = match.get("coordinates", {})
                address_components = match.get("addressComponents", {})

                return ResolvedGeography(
                    level="geocoded_place",
                    filters={},
                    display_name=match.get("matchedAddress", place_name),
                    fips_codes={
                        "state": address_components.get("state"),
                        "county": address_components.get("county"),
                    },
                    confidence=0.95,
                    note="Resolved via Census Geocoding API",
                    geocoding_metadata={
                        "coordinates": coords,
                        "match_type": match.get("matchType"),
                        "api_response": data,
                    },
                )

        except Exception as e:
            logger.debug(f"Geocoding API failed for '{place_name}': {e}")

        return None

    def _search_places_data_api(
        self, place_name: str, state_fips: str = None
    ) -> Optional[ResolvedGeography]:
        """Search places using Census Data API"""
        try:
            # Use cached method instead of direct API call
            if state_fips:
                data = self._get_places_for_state_cached(state_fips)
            else:
                # Fallback to direct API call for nationwide search
                params = {"get": "NAME,GEO_ID", "for": "place:*"}
                response = requests.get(
                    self.data_api_url, params=params, timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()

            place_lower = place_name.lower().strip()
            best_match = None
            best_score = 0

            for row in data[1:]:  # Skip header
                name, geo_id, curr_state_fips, place_fips = row
                name_lower = name.lower()

                # Calculate match score
                score = self._calculate_match_score(place_lower, name_lower)

                if score > best_score and score >= 0.7:  # Minimum threshold
                    best_match = (name, curr_state_fips, place_fips, score)
                    best_score = score

            if best_match:
                name, state_fips, place_fips, score = best_match
                return ResolvedGeography(
                    level="place",
                    filters={
                        "for": f"place:{place_fips}",
                        "in": f"state:{state_fips}",
                    },
                    display_name=name,
                    fips_codes={"state": state_fips, "place": place_fips},
                    confidence=min(0.9, score),
                    note="Resolved via Census Data API",
                    geocoding_metadata={"match_score": score},
                )

        except Exception as e:
            logger.error(f"Data API search failed: {e}")

        return None

    @staticmethod
    def _calculate_match_score(search_term: str, candidate: str) -> float:
        """Calculate fuzzy match score between search term and candidate"""
        # Exact match
        if search_term == candidate:
            return 1.0

        # Contains search term
        if search_term in candidate:
            return 0.9

        # Starts with search term
        if candidate.startswith(search_term):
            return 0.85

        # Simple word overlap score
        search_words = set(search_term.split())
        candidate_words = set(candidate.split())

        if not search_words:
            return 0.0

        overlap = len(search_words.intersection(candidate_words))
        return overlap / len(search_words) * 0.8

    def geocode_place(self, place_name: str, state: str = None) -> ResolvedGeography:
        """
        Geocode a place using multiple Census APIs with fallback strategy

        Args:
            place_name: Name of the place to geocode
            state: Optional state name or abbreviation to narrow search

        Returns:
            ResolvedGeography object with geocoding results
        """
        if not place_name or not place_name.strip():
            return self._create_error_result(place_name, "Empty place name provided")

        place_name = place_name.strip()

        # Strategy 1: Try Census Geocoding API first (most accurate)
        result = self._try_geocoding_api(place_name, state)
        if result:
            return result

        # Strategy 2: Try Census Data API for places
        state_fips = None
        if state:
            state_fips = self._get_state_fips(state)

        result = self._search_places_data_api(place_name, state_fips)
        if result:
            return result

        # No matches found
        return self._create_error_result(
            place_name,
            f"No matches found for '{place_name}'" + (f" in {state}" if state else ""),
        )

    def geocode_county(self, county_name: str, state: str) -> ResolvedGeography:
        """
        Geocode a county using Census Data API

        Args:
            county_name: Name of the county (e.g., "Cook County", "Cook")
            state: State name or abbreviation (required for counties)

        Returns:
            ResolvedGeography object with county geocoding results
        """
        if not county_name or not county_name.strip():
            return self._create_error_result(county_name, "Empty county name provided")

        if not state or not state.strip():
            return self._create_error_result(
                county_name, "State is required for county resolution"
            )

        county_name = county_name.strip()

        try:
            # Get state FIPS first
            state_fips = self._get_state_fips(state)
            if not state_fips:
                return self._create_error_result(
                    county_name, f"Could not resolve state '{state}'"
                )

            # Use cached method instead of direct API call
            data = self._get_counties_for_state_cached(state_fips)

            county_lower = county_name.lower().strip()

            # Remove common suffixes for matching
            county_search = (
                county_lower.replace(" county", "")
                .replace(" parish", "")
                .replace(" borough", "")
            )

            best_match = None
            best_score = 0

            for row in data[1:]:  # Skip header
                name, geo_id, curr_state_fips, county_fips = row
                name_lower = name.lower()

                # Calculate match score for counties
                score = self._calculate_county_match_score(county_search, name_lower)

                if score > best_score and score >= 0.7:  # Minimum threshold
                    best_match = (name, curr_state_fips, county_fips, score)
                    best_score = score

            if best_match:
                name, state_fips, county_fips, score = best_match
                return ResolvedGeography(
                    level="county",
                    filters={
                        "for": f"county:{county_fips}",
                        "in": f"state:{state_fips}",
                    },
                    display_name=name,
                    fips_codes={"state": state_fips, "county": county_fips},
                    confidence=min(0.95, score),
                    note="Resolved via Census Data API",
                    geocoding_metadata={"match_score": score, "entity_type": "county"},
                )

            return self._create_error_result(
                county_name, f"County '{county_name}' not found in {state}"
            )

        except Exception as e:
            logger.error(f"Error geocoding county '{county_name}': {e}")
            return self._create_error_result(county_name, f"API error: {str(e)}")

    def validate_geography_level(
        self, level: str, location_type: str = None, has_county_context: bool = False
    ) -> Tuple[bool, str]:
        """
        Validate if a geography level is supported

        Args:
            level: Geography level (e.g., 'tract', 'county', 'place')
            location_type: Type of location ('city', 'county', 'state')
            has_county_context: Whether county context is available

        Returns:
            (is_valid, message): Validation result and message
        """
        if not level:
            return False, "No geography level specified"

        level_info = self.supported_geography_levels[level]

        # Check if level is supported
        if not level_info["supported"]:
            suggestion = level_info.get("suggestion", "Try a different geography level")
            return (
                False,
                f"Geography level '{level}' is not yet supported. {suggestion}",
            )

        # Check if level requires context but context is not available
        if level_info.get("requires_context") and not has_county_context:
            return (
                False,
                f"Geography level '{level}' requires additional context. {level_info.get('suggestion', 'Please provide more specific location information.')}",
            )

        # All validations passed
        return True, f"Geography level '{level}' is supported"

    def get_geography_level_suggestion(
        self, requested_level: str, location_type: str = None
    ) -> str:
        """Get helpful suggestions for unsupported geography levels"""
        level = requested_level.lower().strip()

        if level in ["tract", "census_tract"]:
            return (
                "Census tract data requires specific county context. Please provide a county name."
                "Try requesting county-level data instead."
                "population of Cook County, Illinois"
            )

        elif level in ["block group", "block_group"]:
            return (
                "Block group data is very granular and requires tract context. "
                "Try county-level data for broader coverage."
            )

        elif level in ["congressional_district", "congressional district", "cd"]:
            return (
                "Congressional district data is available but not yet implemented. "
                "Try state-level data for similar geographic coverage."
            )

        elif level in ["zip", "zipcode", "zcta"]:
            return (
                "ZIP code data is available but requires special handling. "
                "Try city or county-level data instead."
            )

        else:
            return f"Geography level '{requested_level}' is not supported. Try: place, county, state, or nation."

    @staticmethod
    def _calculate_county_match_score(search_term: str, candidate: str) -> float:
        """Calculate match score specifically for counties"""
        # Remove county suffixes from candidate for comparison
        candidate_clean = (
            candidate.replace(" county", "")
            .replace(" parish", "")
            .replace(" borough", "")
        )

        # Exact match (without suffix)
        if search_term == candidate_clean:
            return 1.0

        # Exact match with original search term
        if search_term in candidate:
            return 0.95

        # Starts with search term
        if candidate_clean.startswith(search_term):
            return 0.9

        # Contains search term
        if search_term in candidate_clean:
            return 0.85

        # Word overlap
        search_words = set(search_term.split())
        candidate_words = set(candidate_clean.split())

        if not search_words:
            return 0.0

        overlap = len(search_words.intersection(candidate_words))
        return overlap / len(search_words) * 0.8

    def _create_error_result(
        self, place_name: str, error_msg: str
    ) -> ResolvedGeography:
        """Create a standardized error result"""
        return ResolvedGeography(
            level="error",
            filters={},
            display_name=place_name,
            fips_codes={},
            confidence=0.0,
            note=error_msg,
            geocoding_metadata={},
        )

    def batch_geocode(
        self, places: list, state: str = None
    ) -> Dict[str, ResolvedGeography]:
        """Batch geocode multiple places"""
        results = {}
        for place in places:
            try:
                results[place] = self.geocode_place(place, state)
            except Exception as e:
                logger.error(f"Error geocoding '{place}': {e}")
                results[place] = self._create_error_result(
                    place, f"Processing error: {e}"
                )
        return results

    def get_cache_stats(self) -> dict:
        """Get performance statistics for monitoring"""
        return {
            "state_fips_cache": self._get_state_fips.cache_info()._asdict(),
            "places_cache": self._get_places_for_state_cached.cache_info()._asdict(),
            "counties_cache": self._get_counties_for_state_cached.cache_info()._asdict(),
        }

    def clear_caches(self):
        """Clear all caches (useful for testing)"""
        self._get_state_fips.cache_clear()
        self._get_places_for_state_cached.cache_clear()
        self._get_counties_for_state_cached.cache_clear()


if __name__ == "__main__":
    geocoding_service = CensusGeocodingService()
    print("--------------------------------")
    print(geocoding_service.geocode_place("New York City"))
    print("--------------------------------")
    print(geocoding_service.geocode_place("Chicago"))
    print("--------------------------------")
    print(geocoding_service.geocode_place("Chicago", "Illinois"))
    print("--------------------------------")
    print(geocoding_service.geocode_place("Chicago", "IL"))
    print("--------------------------------")
    print(geocoding_service.geocode_place("Chicago", "IL"))
    print("--------------------------------")
    geocoding_service.geocode_place("Springfield", "Illinois")
    print("--------------------------------")
    print(geocoding_service.geocode_place("Beverly Hills", "California"))
    print("--------------------------------")
    print(geocoding_service.geocode_place("Beverly Hills", "CA"))
    print("-------------GEOCODE PLACE-------------------")
    print(geocoding_service.geocode_county("Cook County", "Illinois"))
    print("--------------------------------")
    print(geocoding_service.geocode_county("Cook County", "IL"))
    print("--------------------------------")
    print(geocoding_service.geocode_county("Cook County", "Illinois"))
    print("--------------------------------")
    print(geocoding_service.geocode_county("Cook County", "IL"))
    print("--------------------------------")
    # Test CSV loading
    print("=== Testing CSV State Resolution ===")
    test_states = [
        "TX",
        "Texas",
        "CA",
        "California",
        "IL",
        "Illinois",
        "DC",
        "District of Columbia",
    ]

    for state in test_states:
        result = geocoding_service._resolve_state_from_csv(state)
        print(f"'{state}' -> '{result}'")

    print("=== Testing Geography Level Validation ===")
    test_cases = [
        ("place", "city", False),  # Should be valid
        ("county", "county", False),  # Should be valid
        ("state", "state", False),  # Should be valid
        ("tract", "county", False),  # Should be invalid - no county context
        ("tract", "county", True),  # Should be invalid - not implemented
        ("block_group", "city", False),  # Should be invalid
        ("nation", None, False),  # Should be valid
    ]

    for level, loc_type, has_county in test_cases:
        is_valid, message = geocoding_service.validate_geography_level(
            level, loc_type, has_county
        )
        status = "✅" if is_valid else "❌"
        print(f"{status} {level:15} + {loc_type or 'None':10} -> {message}")
    # print(geocoding_service.validate_geography_level("place", "New York City"))
    # print("--------------------------------")
    # print(geocoding_service.validate_geography_level("county", "Cook County"))

    # print(geocoding_service.validate_geography_level("state", "Illinois"))
    # print(geocoding_service.validate_geography_level("tract", "Cook County"))
    # print(geocoding_service.validate_geography_level("block_group", "Cook County"))
    # print(geocoding_service.validate_geography_level("block", "Cook County"))
