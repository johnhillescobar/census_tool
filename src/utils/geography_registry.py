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

        parent_geo = parent_geo or self._infer_parent_geo(friendly_name)

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
            alias: self._normalize_name(target)
            for alias, target in raw_aliases.items()
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
