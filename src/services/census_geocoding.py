import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.state.types import ResolvedGeography

logger = logging.getLogger(__name__)


class CensusGeocodingService:
    def geocode_place(self, place_name: str, state: str = None) -> ResolvedGeography:
        # Call Census Geocoding API
        pass

    def geocode_county(self, county_name: str, state: str) -> ResolvedGeography:
        # Resolve county FIPS codes
        pass

    def validate_geography_level(self, level: str, location: str) -> bool:
        # Check if level is supported for this location
        pass


if __name__ == "__main__":
    geocoding_service = CensusGeocodingService()
    print(geocoding_service.geocode_place("New York City"))
    print(geocoding_service.geocode_county("Cook County", "Illinois"))
    print(geocoding_service.validate_geography_level("place", "New York City"))
    print(geocoding_service.validate_geography_level("county", "Cook County"))
    print(geocoding_service.validate_geography_level("state", "Illinois"))
    print(geocoding_service.validate_geography_level("tract", "Cook County"))
    print(geocoding_service.validate_geography_level("block_group", "Cook County"))
    print(geocoding_service.validate_geography_level("block", "Cook County"))
