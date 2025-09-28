import os
import sys
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from functools import lru_cache
from config import (
    CENSUS_GEOCODING_GEOGRAPHY_URL,
    GEOCODING_TIMEOUT,
    MAX_GEOCODING_RETRIES,
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import ResolvedGeography

logger = logging.getLogger(__name__)


class CensusGeocodingService:
    """Enhanced Census Geocoding Service using both geocoding and data APIs"""

    def __init__(self):
        self.geocoding_url = CENSUS_GEOCODING_GEOGRAPHY_URL
        self.data_api_url = "https://api.census.gov/data/2020/dec/pl"
        self.timeout = GEOCODING_TIMEOUT
        self.max_retries = MAX_GEOCODING_RETRIES

    @lru_cache(maxsize=128)
    def _get_state_fips(self, state: str) -> Optional[str]:
        """Get state FIPS code from state name/abbreviation with caching"""
        try:
            params = {"get": "NAME", "for": "state:*"}
            response = requests.get(
                self.data_api_url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            state_lower = state.lower().strip()

            for row in data[1:]:  # Skip header
                state_name, state_fips = row
                state_name_lower = state_name.lower()

                # Match full name or abbreviation
                if (
                    state_lower == state_name_lower
                    or state_name_lower.startswith(state_lower)
                    or len(state_lower) == 2
                    and state_lower in state_name_lower
                ):
                    return state_fips

            return None

        except Exception as e:
            logger.warning(f"Failed to get state FIPS for '{state}': {e}")
            return None

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
            params = {"get": "NAME,GEO_ID", "for": "place:*"}

            if state_fips:
                params["in"] = f"state:{state_fips}"

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
    print("--------------------------------")
    # print(geocoding_service.geocode_county("Cook County", "Illinois"))
    # print(geocoding_service.validate_geography_level("place", "New York City"))
    # print(geocoding_service.validate_geography_level("county", "Cook County"))
    # print(geocoding_service.validate_geography_level("state", "Illinois"))
    # print(geocoding_service.validate_geography_level("tract", "Cook County"))
    # print(geocoding_service.validate_geography_level("block_group", "Cook County"))
    # print(geocoding_service.validate_geography_level("block", "Cook County"))
