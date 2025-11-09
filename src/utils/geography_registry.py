"""
Geography Registry - Dynamic geography discovery and caching
Part of Phase 9F: Census API Flexibility
"""

import requests
import logging
from typing import Dict, Optional, Any
from pathlib import Path
import pickle
import urllib.parse
from datetime import datetime, timedelta

from src.utils.census_api_utils import build_geo_filters

logger = logging.getLogger(__name__)


class GeographyRegistry:
    """
    Discover and cache valid geography levels and area codes from Census API

    This replaces hardcoded geography mappings with dynamic discovery.
    """

    def __init__(self, cache_dir: str = "data/geography_cache"):
        """
        Initialize the geography registry

        Args:
            cache_dir: Directory to store cached geography data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In memory caches
        self.levels_cache = {}
        self.areas_cache = {}

        # Load token mappings
        self.token_map = self._load_token_mappings()

    def _load_token_mappings(self) -> Dict[str, str]:
        """Friendly name → API token mappings"""
        return {
            # Common terms
            "metro area": "metropolitan statistical area/micropolitan statistical area",
            "msa": "metropolitan statistical area/micropolitan statistical area",
            "cbsa": "metropolitan statistical area/micropolitan statistical area",
            "metro": "metropolitan statistical area/micropolitan statistical area",
            "metro division": "metropolitan division",
            "mdiv": "metropolitan division",
            "csa": "combined statistical area",
            "combined statistical area": "combined statistical area",
            "necta": "new england city and town area",
            "necta division": "new england city and town area division",
            "urban area": "urban area",
            # Standard geographies
            "county": "county",
            "counties": "county",
            "place": "place",
            "city": "place",
            "town": "place",
            "cities": "place",
            "state": "state",
            "states": "state",
            # Detailed geographies
            "census tract": "tract",
            "tract": "tract",
            "tracts": "tract",
            "block group": "block group",
            "block groups": "block group",
            "zip code": "zip code tabulation area",
            "zip": "zip code tabulation area",
            "zcta": "zip code tabulation area",
            "puma": "public use microdata area",
            # Districts
            "school district": "school district (unified)",
            "school districts": "school district (unified)",
            "congressional district": "congressional district",
            "congressional districts": "congressional district",
            "state legislative district": "state legislative district (upper chamber)",
            # Subdivisions
            "county subdivision": "county subdivision",
            "county subdivisions": "county subdivision",
            # Tribal
            "tribal tract": "tribal census tract (or part)",
            "tribal tracts": "tribal census tract (or part)",
            "tribal area": "american indian area/alaska native area (reservation or statistical entity only)",
            "tribal areas": "american indian area/alaska native area (reservation or statistical entity only)",
            "reservation": "american indian area/alaska native area (reservation or statistical entity only)",
        }

    def enumerate_areas(
        self,
        dataset: str,
        year: int,
        geo_token: str,
        parent_geo: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Enumerate all areas at a geography level

        Calls Census API: get=NAME,GEO_ID&for={geo_token}:*[&in=...]

        Args:
            dataset: Census dataset (e.g., "acs/acs5")
            year: Year (e.g., 2023)
            geo_token: Geography token (e.g., "county", "place")
            parent_geo: Optional parent geography (e.g., {"state": "06"})
            force_refresh: Force API call even if cached

        Returns:
            Dict mapping area names to metadata:
            {
                "Los Angeles County, California": {
                    "code": "037",
                    "geo_id": "0500000US06037",
                    "full_name": "Los Angeles County, California"
                }
            }

        Example:
            >>> registry.enumerate_areas("acs/acs5", 2023, "county", {"state": "06"})
            {'Los Angeles County, California': {'code': '037', ...}, ...}
        """

        # Build cache key
        if parent_geo:
            # Sort for consistent cache keys - handles all multi-parent cases
            parent_key = ",".join([f"{k}={v}" for k, v in sorted(parent_geo.items())])
        else:
            parent_key = "none"

        cache_key = f"{dataset}:{year}:{geo_token}:{parent_key}"

        # Cache disk cache
        safe_filename = (
            cache_key.replace(":", "_")
            .replace("/", "_")
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )
        cache_file = self.cache_dir / f"{safe_filename}.pkl"

        if not force_refresh and cache_file.exists():
            # Check if cache is recent (less than 30 days old)
            if (
                datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            ) < timedelta(days=30):
                try:
                    with open(cache_file, "rb") as f:
                        areas = pickle.load(f)
                    self.areas_cache[cache_key] = areas
                    logger.info(
                        f"Loaded {len(areas)} areas from disk cache: {geo_token}"
                    )
                    return areas

                except Exception as e:
                    logger.error(f"Error loading cache file {cache_file}: {e}")

        # Call Census API
        logger.info(f"Enumerating areas: {geo_token} for {dataset}/{year}")

        try:
            base_url = f"https://api.census.gov/data/{year}/{dataset}"
            params = ["get=NAME,GEO_ID"]

            filters = build_geo_filters(
                dataset=dataset,
                year=year,
                geo_for={geo_token: "*"},
                geo_in=parent_geo or {},
            )

            params.append(f"for={filters['for']}")
            if filters.get("in"):
                params.append(f"in={filters['in']}")

            url = f"{base_url}?{'&'.join(params)}"

            logger.debug(f"Calling Census API URL: {url}")

            # Make request
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse response
            # Format: [["NAME", "GEO_ID", "CODE"], ["Area 1", "id1", "code1"], ...]
            areas = {}

            if len(data) > 1:
                header = data[0]
                name_idx = header.index("NAME")
                geo_id_idx = header.index("GEO_ID")
                # Last column is usually the code
                code_idx = len(header) - 1

                for row in data[1:]:
                    name = row[name_idx]
                    geo_id = row[geo_id_idx]
                    code = row[code_idx]

                    areas[name] = {"code": code, "geo_id": geo_id, "full_name": name}

                logger.info(f"Enumerated {len(areas)} areas for {geo_token}")

                # Cache results
                self.areas_cache[cache_key] = areas

                # Save to disk
                try:
                    with open(cache_file, "wb") as f:
                        pickle.dump(areas, f)
                    logger.debug(f"Saved {len(areas)} areas to disk cache: {geo_token}")

                except Exception as e:
                    logger.warning(f"Error saving areas to disk cache: {e}")

                return areas

            else:
                logger.warning(f"No areas found for {geo_token}")
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to enumerate areas for {geo_token}: {e}")
            return {}

        except Exception as e:
            logger.error(f"Error enumerating areas: {e}")
            return {}

    def _url_encode_dict(self, text: str) -> str:
        """URL encode spaces and special characters"""
        return urllib.parse.quote(text)

    def _normalize_name(self, name: str) -> str:
        """
        Normalize geography name for fuzzy matching

        - Lowercase
        - Remove common suffixes (County, city, etc.)
        - Strip punctuation
        """

        name = name.lower().strip()

        # Remove common suffixes
        suffixes = [
            "county",
            "city",
            "town",
            "parish",
            "borough",
            "municipality",
            "village",
            "township",
            "district",
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()

        # Remove punctuation
        name = name.replace(",", "").replace(".", "").strip()

        return name

    def find_area_code(
        self,
        friendly_name: str,
        geo_token: str,
        dataset: str,
        year: int,
        parent_geo: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find Census code for a friendly geography name

        Args:
            friendly_name: User-friendly name (e.g., "Los Angeles County")
            geo_token: Geography type (e.g., "county")
            dataset: Census dataset
            year: Year
            parent_geo: Parent geography constraint

        Returns:
            Dict with code and metadata, or None if not found

        Example:
            >>> registry.find_area_code("Los Angeles", "county", "acs/acs5", 2023, {"state": "06"})
            {'code': '037', 'geo_id': '0500000US06037', 'full_name': 'Los Angeles County, California', 'confidence': 0.95}
        """

        # Get all areas at this level
        areas = self.enumerate_areas(dataset, year, geo_token, parent_geo)

        if not areas:
            return None

        # Normalize search term
        search_term = self._normalize_name(friendly_name)

        # Try exact match first
        for full_name, metadata in areas.items():
            if self._normalize_name(full_name) == search_term:
                return {**metadata, "confidence": 1.0, "match_type": "Exact match"}

        # Try partial match
        for full_name, metadata in areas.items():
            if search_term in self._normalize_name(full_name):
                return {**metadata, "confidence": 0.9, "match_type": "Partial match"}

        # Try contains (reversed)
        for full_name, metadata in areas.items():
            if self._normalize_name(search_term) in self._normalize_name(full_name):
                return {**metadata, "confidence": 0.8, "match_type": "Contains match"}

        logger.warning(
            f"No match found for {friendly_name} in {geo_token} for {dataset}/{year}"
        )
        return None
