"""
Dataset-specific geography validation via geography.html scraping with caching and telemetry.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
from bs4 import BeautifulSoup

from src.utils.telemetry import record_event

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Set[str]] = {}
_DISK_CACHE_DIR = Path("data/geography_levels_cache")
_DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(dataset: str, year: int) -> str:
    return f"{dataset}:{year}"


def _load_disk_cache(dataset: str, year: int) -> Optional[Set[str]]:
    key = _cache_key(dataset, year)
    path = _DISK_CACHE_DIR / f"{key.replace('/', '_')}.pkl"
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            return pickle.load(fh)
    except Exception as exc:
        logger.warning("Failed to read geography cache %s: %s", path, exc)
        return None


def _save_disk_cache(dataset: str, year: int, levels: Set[str]) -> None:
    key = _cache_key(dataset, year)
    path = _DISK_CACHE_DIR / f"{key.replace('/', '_')}.pkl"
    try:
        with path.open("wb") as fh:
            pickle.dump(levels, fh)
    except Exception as exc:
        logger.warning("Failed to persist geography cache %s: %s", path, exc)


def _normalize_level(token: str) -> str:
    return " ".join(token.strip().lower().split())


def _parse_geography_levels(html_text: str) -> Set[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    levels: Set[str] = set()

    # geography.html contains tables with Summary Level and Geography entries
    for table in soup.find_all("table"):
        headers = [
            header.get_text(" ", strip=True).lower()
            for header in table.find_all("th")
        ]
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
            if not cells:
                continue
            mapping = dict(zip(headers, cells))
            geo_value = mapping.get("geography") or mapping.get("name")
            if geo_value:
                levels.add(_normalize_level(geo_value))
    return levels


def fetch_dataset_geography_levels(dataset: str, year: int, *, force_refresh: bool = False) -> Set[str]:
    """
    Fetch the set of supported geography levels for dataset/year using geography.html.
    """
    dataset = dataset.strip()
    key = _cache_key(dataset, year)

    if not force_refresh:
        if key in _CACHE:
            return _CACHE[key]
        disk_cache = _load_disk_cache(dataset, year)
        if disk_cache is not None:
            _CACHE[key] = disk_cache
            return disk_cache

    url = f"https://api.census.gov/data/{year}/{dataset}/geography.html"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        levels = _parse_geography_levels(response.text)
        if not levels:
            logger.warning("No geography levels parsed for %s", url)
        _CACHE[key] = levels
        _save_disk_cache(dataset, year, levels)
        record_event(
            "dataset_geography_levels",
            {
                "dataset": dataset,
                "year": year,
                "level_count": len(levels),
                "source": "network",
            },
        )
        return levels
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        record_event(
            "dataset_geography_levels",
            {
                "dataset": dataset,
                "year": year,
                "level_count": 0,
                "source": "error",
                "error": str(exc),
            },
        )
        # fallback to cached version if available
        if key in _CACHE:
            return _CACHE[key]
        disk_cache = _load_disk_cache(dataset, year)
        if disk_cache is not None:
            _CACHE[key] = disk_cache
            return disk_cache
        return set()


def geography_supported(dataset: str, year: int, geography_level: str) -> Dict[str, object]:
    """
    Check if a geography level is supported for a dataset/year.
    """
    levels = fetch_dataset_geography_levels(dataset, year)
    normalized_level = _normalize_level(geography_level)
    supported = normalized_level in levels
    return {
        "dataset": dataset,
        "year": year,
        "geography_level": geography_level,
        "normalized_level": normalized_level,
        "supported": supported,
        "available_levels": sorted(levels),
    }


__all__ = ["fetch_dataset_geography_levels", "geography_supported"]

