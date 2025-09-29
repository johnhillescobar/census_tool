import os
import sys
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import GeographyRequest, ResolvedGeography
from src.services.census_geocoding import CensusGeocodingService
from src.utils.geo_parser import GeographyParser

logger = logging.getLogger(__name__)


class DynamicGeographyResolver:
    """Orchestrate the dynamic resolution process"""

    def __init__(self):
        self.geocoding_service = CensusGeocodingService()
        self.parser = GeographyParser()

        # Fallback to static mappings for special cases
        self.static_fallbacks = {
            "nation": {
                "level": "nation",
                "filters": {"for": "us:1"},
                "note": "United States",
            },
            "national": {
                "level": "nation",
                "filters": {"for": "us:1"},
                "note": "United States",
            },
            "usa": {
                "level": "nation",
                "filters": {"for": "us:1"},
                "note": "United States",
            },
            "united_states": {
                "level": "nation",
                "filters": {"for": "us:1"},
                "note": "United States",
            },
        }

    def resolve_geography_from_text(self, text: str) -> ResolvedGeography:
        """Main entry point: resolve geography from raw text"""

        # Parse the text into structured request
        geo_request = self.parser.parse_query(text)

        # Resolve using the structured request
        return self.resolve_geography(geo_request)

    def resolve_geography(self, geo_request: GeographyRequest) -> ResolvedGeography:
        """Resolve geography from parsed GeographyRequest"""

        try:
            is_valid = True
            message = ""

            # Validate requested level first
            if geo_request.requested_level:
                is_valid, message = self.geocoding_service.validate_geography_level(
                    geo_request.requested_level,
                    location_type=geo_request.entities[0].type
                    if geo_request.entities
                    else None,
                )

                if not is_valid:
                    return self._create_error_result(message)

            # Handle nationwide/national queries
            if self._is_nationwide_query(geo_request):
                return self._create_nationwide_result()

            # Process geographic entities
            if not geo_request.entities:
                return self._create_error_result(
                    "No geographic entities found in query"
                )

            # Try to resolve the primary entity
            primary_entity = geo_request.entities[
                0
            ]  # Take the first/most confident entity

            if primary_entity.type == "city":
                return self._resolve_city(primary_entity, geo_request.state_context)
            elif primary_entity.type == "county":
                return self._resolve_county(primary_entity, geo_request.state_context)
            elif primary_entity.type == "state":
                return self._resolve_state(primary_entity)
            else:
                # Try as a general place
                return self._resolve_place(primary_entity, geo_request.state_context)

        except Exception as e:
            logger.error(f"Error in geography resolution: {e}")
            return self._create_error_result(f"Resolution error: {str(e)}")

    def _is_nationwide_query(self, geo_request: GeographyRequest) -> bool:
        """Check if this is a nationwide query"""
        text_lower = geo_request.raw_text.lower()
        nationwide_keywords = [
            "nationwide",
            "national",
            "usa",
            "united states",
            "country",
        ]
        return any(keyword in text_lower for keyword in nationwide_keywords)

    def _resolve_city(self, entity, state_context: Optional[str]) -> ResolvedGeography:
        """Resolve city/place entities"""
        return self.geocoding_service.geocode_place(entity.name, state_context)

    def _resolve_place(self, entity, state_context: Optional[str]) -> ResolvedGeography:
        """Resolve general place entities"""
        return self.geocoding_service.geocode_place(entity.name, state_context)

    def _resolve_county(
        self, entity, state_context: Optional[str]
    ) -> ResolvedGeography:
        """Resolve county entities (future implementation)"""
        # For now, return error - will implement in Phase 6C
        return self._create_error_result(
            f"County-level resolution not yet implemented for '{entity.name}'"
        )

    def _resolve_state(self, entity) -> ResolvedGeography:
        """Resolve state entities"""
        # Use the geocoding service's state resolution
        try:
            state_fips = self.geocoding_service._get_state_fips(entity.name)
            return ResolvedGeography(
                level="state",
                filters={"for": f"state:{state_fips}"},
                display_name=entity.name,
                fips_codes={"state": state_fips},
                confidence=0.95,
                note="State resolved via dynamic lookup",
                geocoding_metadata={"entity_type": "state"},
            )
        except Exception as e:
            return self._create_error_result(
                f"Could not resolve state '{entity.name}': {str(e)}"
            )

    def _create_nationwide_result(self) -> ResolvedGeography:
        """Create result for nationwide queries"""
        return ResolvedGeography(
            level="nation",
            filters={"for": "us:1"},
            display_name="United States",
            fips_codes={"nation": "1"},
            confidence=1.0,
            note="Nationwide query resolved",
            geocoding_metadata={"query_type": "nationwide"},
        )

    def _create_error_result(self, error_msg: str) -> ResolvedGeography:
        """Create standardized error result"""
        return ResolvedGeography(
            level="nation",
            filters={"for": "us:1"},
            display_name="United States",
            fips_codes={"nation": "us"},
            confidence=0.8,
            note="No geography specified - using national level as default",
            geocoding_metadata={},
        )


# Backward compatibility function for existing geo_node
def resolve_geography_hint(geo_hint: str, profile_default_geo: dict = None) -> dict:
    """
    Backward compatibility wrapper for existing geo_node integration

    This function maintains the same interface as the old static resolver
    but uses the new dynamic resolution system underneath.
    """

    resolver = DynamicGeographyResolver()

    try:
        # Use new dynamic resolution
        result = resolver.resolve_geography_from_text(geo_hint)

        # Convert ResolvedGeography back to old dict format
        return {
            "level": result.level,
            "filters": result.filters,
            "note": result.note,
            "confidence": result.confidence,
            "fips_codes": result.fips_codes,
        }

    except Exception as e:
        logger.error(f"Dynamic resolution failed, using profile default: {e}")

        # Fallback to profile default if available
        if profile_default_geo:
            return profile_default_geo

        # Final fallback
        return {
            "level": "error",
            "filters": {},
            "note": f"Could not resolve geography: {str(e)}",
            "confidence": 0.0,
            "fips_codes": {},
        }


if __name__ == "__main__":
    resolver = DynamicGeographyResolver()
    places = [
        "New York City",
        "Chicago",
        "Los Angeles",
        "Houston, TX",
        "Philadelphia",
        "Naperville",
        "Springfield",
        "Rochester, NY",
        "Rochester, MN",
        "Rochester",
    ]
    for place in places:
        result = resolver.resolve_geography_from_text(place)
        print(result)
