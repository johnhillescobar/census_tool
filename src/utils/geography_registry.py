"""
Geography Registry - Dynamic geography discovery and caching
Part of Phase 9F: Census API Flexibility
"""

import logging
import pickle
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import us
from rapidfuzz import fuzz, process

from src.utils.census_api_utils import build_geo_filters
from src.utils.chroma_utils import validate_and_fix_geo_params
from src.utils.telemetry import record_event

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
            # Tribal geographies (comprehensive)
            "tribal tract": "tribal census tract",
            "tribal tracts": "tribal census tract",
            "tribal census tract": "tribal census tract",
            "tribal census tract or part": "tribal census tract (or part)",
            "tribal census tract (or part)": "tribal census tract (or part)",
            "tribal block group": "tribal block group",
            "tribal block groups": "tribal block group",
            "tribal block group or part": "tribal block group (or part)",
            "tribal block group (or part)": "tribal block group (or part)",
            "tribal subdivision": "tribal subdivision/remainder",
            "tribal subdivision/remainder": "tribal subdivision/remainder",
            "tribal area": "american indian area/alaska native area/hawaiian home land",
            "tribal areas": "american indian area/alaska native area/hawaiian home land",
            "american indian area": "american indian area/alaska native area/hawaiian home land",
            "alaska native area": "american indian area/alaska native area/hawaiian home land",
            "hawaiian home land": "american indian area/alaska native area/hawaiian home land",
            "aiannh": "american indian area/alaska native area/hawaiian home land",
            "reservation": "american indian area/alaska native area (reservation or statistical entity only)",
            "reservations": "american indian area/alaska native area (reservation or statistical entity only)",
            "tribal reservation": "american indian area/alaska native area (reservation or statistical entity only)",
            "american indian reservation": "american indian area/alaska native area (reservation or statistical entity only)",
            "trust land": "american indian area (off-reservation trust land only)/hawaiian home land",
            "trust lands": "american indian area (off-reservation trust land only)/hawaiian home land",
            "off-reservation trust land": "american indian area (off-reservation trust land only)/hawaiian home land",
            "alaska native regional corporation": "alaska native regional corporation",
            "anrc": "alaska native regional corporation",
            # Statistical areas with (or part) variants
            "metropolitan statistical area": "metropolitan statistical area/micropolitan statistical area",
            "micropolitan statistical area": "metropolitan statistical area/micropolitan statistical area",
            "metropolitan division": "metropolitan division",
            "metropolitan division or part": "metropolitan division (or part)",
            "metropolitan division (or part)": "metropolitan division (or part)",
            "combined statistical area or part": "combined statistical area (or part)",
            "combined statistical area (or part)": "combined statistical area (or part)",
            # (or part) geography variants
            "state or part": "state (or part)",
            "state (or part)": "state (or part)",
            "county or part": "county (or part)",
            "county (or part)": "county (or part)",
            "place or part": "place (or part)",
            "place (or part)": "place (or part)",
            "place/remainder or part": "place/remainder (or part)",
            "place/remainder (or part)": "place/remainder (or part)",
            "principal city or part": "principal city (or part)",
            "principal city (or part)": "principal city (or part)",
            "msa or part": "metropolitan statistical area/micropolitan statistical area (or part)",
            "metropolitan statistical area/micropolitan statistical area (or part)": "metropolitan statistical area/micropolitan statistical area (or part)",
            "aiannh or part": "american indian area/alaska native area/hawaiian home land (or part)",
            "american indian area/alaska native area/hawaiian home land (or part)": "american indian area/alaska native area/hawaiian home land (or part)",
            "tribal area or part": "american indian area/alaska native area (reservation or statistical entity only) (or part)",
            "american indian area/alaska native area (reservation or statistical entity only) (or part)": "american indian area/alaska native area (reservation or statistical entity only) (or part)",
            "trust land or part": "american indian area (off-reservation trust land only)/hawaiian home land (or part)",
            "american indian area (off-reservation trust land only)/hawaiian home land (or part)": "american indian area (off-reservation trust land only)/hawaiian home land (or part)",
            # Additional common variants
            "consolidated city": "consolidated city",
            "subminor civil division": "subminor civil division",
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

        # Normalize geography parameters and enforce hierarchy ordering
        for_token, for_value, ordered_in = validate_and_fix_geo_params(
            dataset=dataset,
            year=year,
            geo_for={geo_token: "*"},
            geo_in=parent_geo,
        )

        parent_key = (
            ",".join(f"{token}={value}" for token, value in ordered_in)
            if ordered_in
            else "none"
        )

        cache_key = f"{dataset}:{year}:{for_token}:{parent_key}"

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
                    record_event(
                        "enumerate_areas",
                        {
                            "dataset": dataset,
                            "year": year,
                            "for_level": for_token,
                            "parent_levels": ordered_in,
                            "url": None,
                            "area_count": len(areas),
                            "cache_hit": True,
                        },
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
                geo_for={for_token: for_value},
                geo_in=dict(ordered_in),
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

                record_event(
                    "enumerate_areas",
                    {
                        "dataset": dataset,
                        "year": year,
                        "for_level": for_token,
                        "parent_levels": ordered_in,
                        "url": url,
                        "area_count": len(areas),
                        "cache_hit": False,
                    },
                )
                return areas

            else:
                logger.warning(f"No areas found for {geo_token}")
                record_event(
                    "enumerate_areas",
                    {
                        "dataset": dataset,
                        "year": year,
                        "for_level": for_token,
                        "parent_levels": ordered_in,
                        "url": url,
                        "area_count": 0,
                        "warning": "empty_response",
                    },
                )
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to enumerate areas for {geo_token}: {e}")
            record_event(
                "enumerate_areas",
                {
                    "dataset": dataset,
                    "year": year,
                    "for_level": for_token,
                    "parent_levels": ordered_in,
                    "url": url,
                    "area_count": 0,
                    "error": str(e),
                },
            )
            return {}

        except Exception as e:
            logger.error(f"Error enumerating areas: {e}")
            record_event(
                "enumerate_areas",
                {
                    "dataset": dataset,
                    "year": year,
                    "for_level": for_token,
                    "parent_levels": ordered_in,
                    "url": url if "url" in locals() else None,
                    "area_count": 0,
                    "error": str(e),
                },
            )
            return {}

    def enumerate_tribal_areas(
        self,
        dataset: str,
        year: int,
        geo_token: str = "american indian area/alaska native area/hawaiian home land",
        state_code: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Enumerate tribal areas with support for special code suffixes

        Args:
            dataset: Census dataset (e.g., "acs/acs5")
            year: Year (e.g., 2023)
            geo_token: Tribal geography type
            state_code: Optional state FIPS code to filter results
            force_refresh: Force API call even if cached

        Returns:
            Dict mapping tribal area names to metadata with code suffixes

        Example:
            >>> registry.enumerate_tribal_areas("acs/acs5", 2023, state_code="40")
            {'Absentee-Shawnee OTSA': {'code': '0010', 'geo_id': '...', 'full_name': '...', 'suffix': None}, ...}
        """
        parent_geo = {"state": state_code} if state_code else None

        # Use standard enumerate_areas but with 7-day cache TTL
        cache_key = f"{dataset}:{year}:{geo_token}:{state_code or 'all'}"
        safe_filename = (
            cache_key.replace(":", "_")
            .replace("/", "_")
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )
        cache_file = self.cache_dir / f"{safe_filename}.pkl"

        if not force_refresh and cache_file.exists():
            # Check if cache is recent (less than 7 days old for tribal areas)
            if (
                datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            ) < timedelta(days=7):
                try:
                    with open(cache_file, "rb") as f:
                        areas = pickle.load(f)
                    logger.info(
                        f"Loaded {len(areas)} tribal areas from disk cache: {geo_token}"
                    )
                    return areas
                except Exception as e:
                    logger.error(f"Error loading cache file {cache_file}: {e}")

        # Call Census API
        logger.info(f"Enumerating tribal areas: {geo_token} for {dataset}/{year}")

        try:
            base_url = f"https://api.census.gov/data/{year}/{dataset}"
            params = ["get=NAME,GEO_ID"]

            # Build geography filters
            filters = build_geo_filters(
                dataset=dataset,
                year=year,
                geo_for={geo_token: "*"},
                geo_in=parent_geo,
            )

            params.append(f"for={filters['for']}")
            if filters.get("in"):
                params.append(f"in={filters['in']}")

            url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Calling Census API URL: {url}")

            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            areas = {}

            if len(data) > 1:
                header = data[0]
                name_idx = header.index("NAME")
                geo_id_idx = header.index("GEO_ID")
                code_idx = len(header) - 1

                for row in data[1:]:
                    name = row[name_idx]
                    geo_id = row[geo_id_idx]
                    code = row[code_idx]

                    # Detect suffix (R for reservation, T for trust land)
                    suffix = None
                    if code.endswith("R"):
                        suffix = "R"
                        code_base = code[:-1]
                    elif code.endswith("T"):
                        suffix = "T"
                        code_base = code[:-1]
                    else:
                        code_base = code

                    areas[name] = {
                        "code": code,
                        "code_base": code_base,
                        "suffix": suffix,
                        "geo_id": geo_id,
                        "full_name": name,
                    }

                logger.info(f"Enumerated {len(areas)} tribal areas for {geo_token}")

                # Save to disk with 7-day TTL
                try:
                    with open(cache_file, "wb") as f:
                        pickle.dump(areas, f)
                    logger.debug(f"Saved {len(areas)} tribal areas to disk cache")
                except Exception as e:
                    logger.warning(f"Error saving tribal areas to disk cache: {e}")

                record_event(
                    "enumerate_tribal_areas",
                    {
                        "dataset": dataset,
                        "year": year,
                        "geo_token": geo_token,
                        "state_code": state_code,
                        "area_count": len(areas),
                        "cache_hit": False,
                    },
                )
                return areas
            else:
                logger.warning(f"No tribal areas found for {geo_token}")
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to enumerate tribal areas: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error enumerating tribal areas: {e}")
            return {}

    def resolve_tribal_area(
        self,
        name: str,
        dataset: str,
        year: int,
        geo_token: str = "american indian area/alaska native area/hawaiian home land",
        state_code: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve tribal area name to Census code with fuzzy matching

        Args:
            name: Tribal area name (e.g., "Navajo Nation")
            dataset: Census dataset
            year: Year
            geo_token: Tribal geography type
            state_code: Optional state FIPS code to narrow search

        Returns:
            Dict with code, suffix, and metadata, or None if not found

        Example:
            >>> registry.resolve_tribal_area("Navajo", "acs/acs5", 2023)
            {'code': '5620R', 'code_base': '5620', 'suffix': 'R', 'confidence': 0.92, ...}
        """
        areas = self.enumerate_tribal_areas(dataset, year, geo_token, state_code)

        if not areas:
            return None

        # Normalize search term
        normalized = name.lower().strip()

        # Try exact match first
        for area_name, metadata in areas.items():
            if area_name.lower() == normalized:
                return {**metadata, "confidence": 1.0, "match_type": "exact"}

        # Fuzzy match using rapidfuzz with multiple scorers to handle partial matches
        choices = list(areas.keys())
        best_match = None
        best_score = 0

        for candidate in choices:
            scores = (
                fuzz.WRatio(name, candidate),
                fuzz.partial_ratio(name, candidate),
                fuzz.token_set_ratio(name, candidate),
            )
            candidate_score = max(scores)
            if candidate_score > best_score:
                best_score = candidate_score
                best_match = candidate

        if best_match and best_score >= 60:
            confidence = best_score / 100.0
            metadata = areas[best_match]

            logger.info(
                f"Matched '{name}' to '{best_match}' (confidence: {confidence:.2f})"
            )

            record_event(
                "resolve_tribal_area",
                {
                    "search_term": name,
                    "matched_name": best_match,
                    "confidence": confidence,
                    "geo_token": geo_token,
                },
            )

            return {
                **metadata,
                "confidence": confidence,
                "match_type": "fuzzy",
                "matched_name": best_match,
            }

        logger.warning(f"No match found for tribal area: {name}")
        return None

    def _cache_tribal_areas(
        self,
        dataset: str,
        year: int,
        geo_token: str,
        state_code: Optional[str] = None,
    ) -> None:
        """
        Pre-cache tribal areas for faster lookups

        Args:
            dataset: Census dataset
            year: Year
            geo_token: Tribal geography type
            state_code: Optional state FIPS code
        """
        logger.info(f"Pre-caching tribal areas: {geo_token} for {dataset}/{year}")
        self.enumerate_tribal_areas(
            dataset, year, geo_token, state_code, force_refresh=True
        )

    def enumerate_statistical_areas(
        self,
        area_type: str,
        dataset: str,
        year: int,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Enumerate statistical areas (CBSAs, CSAs, urban areas)

        Args:
            area_type: Type of statistical area (e.g., "metropolitan statistical area/micropolitan statistical area", "combined statistical area", "urban area")
            dataset: Census dataset
            year: Year
            force_refresh: Force API call even if cached

        Returns:
            Dict mapping area names to metadata

        Example:
            >>> registry.enumerate_statistical_areas("metropolitan statistical area/micropolitan statistical area", "acs/acs5", 2023)
            {'New York-Newark-Jersey City, NY-NJ-PA Metro Area': {'code': '35620', ...}, ...}
        """
        cache_key = f"{dataset}:{year}:{area_type}"
        safe_filename = (
            cache_key.replace(":", "_")
            .replace("/", "_")
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )
        cache_file = self.cache_dir / f"{safe_filename}.pkl"

        if not force_refresh and cache_file.exists():
            # Check if cache is recent (less than 30 days old for statistical areas)
            if (
                datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            ) < timedelta(days=30):
                try:
                    with open(cache_file, "rb") as f:
                        areas = pickle.load(f)
                    logger.info(
                        f"Loaded {len(areas)} statistical areas from disk cache: {area_type}"
                    )
                    return areas
                except Exception as e:
                    logger.error(f"Error loading cache file {cache_file}: {e}")

        # Call Census API
        logger.info(f"Enumerating statistical areas: {area_type} for {dataset}/{year}")

        try:
            base_url = f"https://api.census.gov/data/{year}/{dataset}"
            params = ["get=NAME,GEO_ID"]

            filters = build_geo_filters(
                dataset=dataset,
                year=year,
                geo_for={area_type: "*"},
                geo_in=None,
            )

            params.append(f"for={filters['for']}")

            url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Calling Census API URL: {url}")

            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            areas = {}

            if len(data) > 1:
                header = data[0]
                name_idx = header.index("NAME")
                geo_id_idx = header.index("GEO_ID")
                code_idx = len(header) - 1

                for row in data[1:]:
                    name = row[name_idx]
                    geo_id = row[geo_id_idx]
                    code = row[code_idx]

                    areas[name] = {
                        "code": code,
                        "geo_id": geo_id,
                        "full_name": name,
                    }

                logger.info(
                    f"Enumerated {len(areas)} statistical areas for {area_type}"
                )

                # Save to disk with 30-day TTL
                try:
                    with open(cache_file, "wb") as f:
                        pickle.dump(areas, f)
                    logger.debug(f"Saved {len(areas)} statistical areas to disk cache")
                except Exception as e:
                    logger.warning(f"Error saving statistical areas to disk cache: {e}")

                record_event(
                    "enumerate_statistical_areas",
                    {
                        "dataset": dataset,
                        "year": year,
                        "area_type": area_type,
                        "area_count": len(areas),
                        "cache_hit": False,
                    },
                )
                return areas
            else:
                logger.warning(f"No statistical areas found for {area_type}")
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to enumerate statistical areas: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error enumerating statistical areas: {e}")
            return {}

    def resolve_statistical_area(
        self,
        name: str,
        area_type: str,
        dataset: str,
        year: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve statistical area name to Census code with fuzzy matching

        Args:
            name: Statistical area name (e.g., "New York metro")
            area_type: Type of statistical area
            dataset: Census dataset
            year: Year

        Returns:
            Dict with code and metadata, or None if not found

        Example:
            >>> registry.resolve_statistical_area("New York", "metropolitan statistical area/micropolitan statistical area", "acs/acs5", 2023)
            {'code': '35620', 'confidence': 0.95, ...}
        """
        areas = self.enumerate_statistical_areas(area_type, dataset, year)

        if not areas:
            return None

        # Normalize search term
        normalized = name.lower().strip()

        # Try exact match first
        for area_name, metadata in areas.items():
            if area_name.lower() == normalized:
                return {**metadata, "confidence": 1.0, "match_type": "exact"}

        # Fuzzy match using rapidfuzz
        choices = list(areas.keys())
        result = process.extractOne(
            name,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=70,
        )

        if result:
            matched_name, score, _ = result
            confidence = score / 100.0
            metadata = areas[matched_name]

            logger.info(
                f"Matched '{name}' to '{matched_name}' (confidence: {confidence:.2f})"
            )

            record_event(
                "resolve_statistical_area",
                {
                    "search_term": name,
                    "matched_name": matched_name,
                    "confidence": confidence,
                    "area_type": area_type,
                },
            )

            return {
                **metadata,
                "confidence": confidence,
                "match_type": "fuzzy",
                "matched_name": matched_name,
            }

        logger.warning(f"No match found for statistical area: {name}")
        return None

    def _cache_statistical_areas(
        self,
        area_type: str,
        dataset: str,
        year: int,
    ) -> None:
        """
        Pre-cache statistical areas for faster lookups

        Args:
            area_type: Type of statistical area
            dataset: Census dataset
            year: Year
        """
        logger.info(f"Pre-caching statistical areas: {area_type} for {dataset}/{year}")
        self.enumerate_statistical_areas(area_type, dataset, year, force_refresh=True)

    def _resolve_part_geography(
        self,
        child_token: str,
        parent_token: str,
        parent_code: str,
        dataset: str,
        year: int,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Resolve "(or part)" geography under a parent statistical area

        Args:
            child_token: Child geography token (e.g., "county (or part)")
            parent_token: Parent geography token (e.g., "metropolitan statistical area/micropolitan statistical area")
            parent_code: Parent area code
            dataset: Census dataset
            year: Year

        Returns:
            Dict mapping child area names to metadata

        Example:
            >>> registry._resolve_part_geography("county (or part)", "metropolitan statistical area/micropolitan statistical area", "35620", "acs/acs5", 2023)
            {'Bronx County, NY': {'code': '005', ...}, ...}
        """
        logger.info(f"Resolving {child_token} under {parent_token}={parent_code}")

        try:
            base_url = f"https://api.census.gov/data/{year}/{dataset}"
            params = ["get=NAME,GEO_ID"]

            filters = build_geo_filters(
                dataset=dataset,
                year=year,
                geo_for={child_token: "*"},
                geo_in={parent_token: parent_code},
            )

            params.append(f"for={filters['for']}")
            if filters.get("in"):
                params.append(f"in={filters['in']}")

            url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Calling Census API URL: {url}")

            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            areas = {}

            if len(data) > 1:
                header = data[0]
                name_idx = header.index("NAME")
                geo_id_idx = header.index("GEO_ID")
                code_idx = len(header) - 1

                for row in data[1:]:
                    name = row[name_idx]
                    geo_id = row[geo_id_idx]
                    code = row[code_idx]

                    areas[name] = {
                        "code": code,
                        "geo_id": geo_id,
                        "full_name": name,
                        "parent_token": parent_token,
                        "parent_code": parent_code,
                    }

                logger.info(f"Resolved {len(areas)} {child_token} areas")
                return areas
            else:
                logger.warning(
                    f"No {child_token} areas found under {parent_token}={parent_code}"
                )
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to resolve {child_token}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error resolving {child_token}: {e}")
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

    def _build_aliases(self) -> Dict[str, str]:
        raw_aliases = {
            "nyc": "new york city, new york",
            "new york city": "new york city, new york",
            "manhattan": "new york county, new york",
            "la": "los angeles county, california",
            "los angeles": "los angeles county, california",
            "sf": "san francisco county, california",
        }
        return {
            alias: self._normalize_name(target) for alias, target in raw_aliases.items()
        }

    def _composite_aliases(self):
        return {
            "new york city, new york": [
                ("county", "Bronx County", {"state": "36"}),
                ("county", "Kings County", {"state": "36"}),
                ("county", "New York County", {"state": "36"}),
                ("county", "Queens County", {"state": "36"}),
                ("county", "Richmond County", {"state": "36"}),
            ]
        }

    def _infer_parent_geo(self, friendly_name: str) -> Dict[str, str]:
        if "," not in friendly_name:
            return {}
        parts = [part.strip() for part in friendly_name.split(",")]
        if len(parts) < 2:
            return {}
        state_part = parts[-1]
        state = us.states.lookup(state_part)
        if state and state.fips:
            return {"state": state.fips}
        return {}

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

        if parent_geo is None:
            parent_geo = self._infer_parent_geo(friendly_name) or {}

        # Route to specialized methods for tribal and statistical areas
        tribal_tokens = {
            "american indian area/alaska native area/hawaiian home land",
            "american indian area/alaska native area (reservation or statistical entity only)",
            "american indian area (off-reservation trust land only)/hawaiian home land",
            "tribal subdivision/remainder",
            "tribal census tract",
            "tribal census tract (or part)",
            "tribal block group",
            "tribal block group (or part)",
            "alaska native regional corporation",
        }

        statistical_area_tokens = {
            "metropolitan statistical area/micropolitan statistical area",
            "metropolitan division",
            "combined statistical area",
            "urban area",
        }

        if geo_token in tribal_tokens:
            state_code = parent_geo.get("state") if parent_geo else None
            return self.resolve_tribal_area(
                friendly_name, dataset, year, geo_token, state_code
            )

        if geo_token in statistical_area_tokens:
            return self.resolve_statistical_area(
                friendly_name, geo_token, dataset, year
            )

        # Get all areas at this level
        areas = self.enumerate_areas(dataset, year, geo_token, parent_geo)

        if not areas:
            return None

        # Normalize search term
        normalized = self._normalize_name(friendly_name)
        aliases = self._build_aliases()
        normalized = aliases.get(normalized, normalized)

        composite_aliases = self._composite_aliases()
        composite = composite_aliases.get(normalized)
        if composite:
            components = []
            for token, name, comp_parent in composite:
                component = self.find_area_code(
                    name,
                    token,
                    dataset,
                    year,
                    comp_parent,
                )
                if component:
                    components.append(component)
            if components:
                composite_result = {
                    **components[0],
                    "match_type": "Composite",
                    "confidence": 1.0,
                    "components": components,
                }
                record_event(
                    "geography_match",
                    {
                        "query": friendly_name,
                        "normalized_query": normalized,
                        "match_full_name": components[0]["full_name"],
                        "confidence": composite_result["confidence"],
                        "match_type": "Composite",
                        "geo_token": geo_token,
                        "dataset": dataset,
                        "year": year,
                        "component_count": len(components),
                    },
                )
                return composite_result

        candidates = [
            (full_name, metadata, self._normalize_name(full_name))
            for full_name, metadata in areas.items()
        ]

        # Exact match
        for full_name, metadata, norm in candidates:
            if norm == normalized:
                metadata = {**metadata, "confidence": 1.0, "match_type": "Exact match"}
                record_event(
                    "geography_match",
                    {
                        "query": friendly_name,
                        "normalized_query": normalized,
                        "match_full_name": full_name,
                        "confidence": metadata["confidence"],
                        "match_type": metadata["match_type"],
                        "geo_token": geo_token,
                        "dataset": dataset,
                        "year": year,
                    },
                )
                return metadata

        # Fuzzy matching
        candidate_map = {full_name: norm for full_name, _, norm in candidates}
        match_result = process.extractOne(
            normalized,
            candidate_map,
            scorer=fuzz.token_sort_ratio,
        )

        if match_result:
            match, score, _ = match_result
        else:
            match, score = None, 0

        if match and score >= 80:
            full_name = match
            metadata = next(
                (md for name, md, _ in candidates if name == full_name), None
            )
            if metadata is None:
                logger.warning(
                    "Fuzzy match %s not found in candidates for %s/%s",
                    full_name,
                    geo_token,
                    normalized,
                )
                record_event(
                    "geography_match",
                    {
                        "query": friendly_name,
                        "normalized_query": normalized,
                        "match_full_name": None,
                        "confidence": 0.0,
                        "match_type": "No match",
                        "geo_token": geo_token,
                        "dataset": dataset,
                        "year": year,
                    },
                )
                return None
            result = {
                **metadata,
                "confidence": round(score / 100, 2),
                "match_type": "Fuzzy match",
            }
            record_event(
                "geography_match",
                {
                    "query": friendly_name,
                    "normalized_query": normalized,
                    "match_full_name": full_name,
                    "confidence": result["confidence"],
                    "match_type": result["match_type"],
                    "geo_token": geo_token,
                    "dataset": dataset,
                    "year": year,
                },
            )
            return result

        logger.warning(
            f"No match found for {friendly_name} in {geo_token} for {dataset}/{year}"
        )
        record_event(
            "geography_match",
            {
                "query": friendly_name,
                "normalized_query": normalized,
                "match_full_name": None,
                "confidence": 0.0,
                "match_type": "No match",
                "geo_token": geo_token,
                "dataset": dataset,
                "year": year,
            },
        )
        return None
