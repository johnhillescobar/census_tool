"""
Memory management utility functions for the Census app
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from src.utils.file_utils import load_json_file, save_json_file
from src.utils.time_utils import is_older_than

logger = logging.getLogger(__name__)


def prune_history_by_age(history: List[Dict], retention_days: int) -> List[Dict]:
    """Remove history entries older than retention_days"""
    if not history:
        return []

    pruned = []
    for entry in history:
        try:
            if not is_older_than(entry.get("timestamp"), retention_days):
                pruned.append(entry)
        except Exception as e:
            logger.warning(f"Error processing history entry: {e}")
            continue

    return pruned


def prune_cache_by_age(cache_index: Dict, retention_days: int) -> Dict:
    """Remove cache entries older than retention_days and delete files"""
    if not cache_index:
        return {}

    pruned_cache = {}
    for signature, metadata in cache_index.items():
        try:
            if not is_older_than(metadata.get("timestamp"), retention_days):
                pruned_cache[signature] = metadata
            else:
                # Delete the cached file
                file_path = metadata.get("file_path")
                if file_path and Path(file_path).exists():
                    try:
                        Path(file_path).unlink()
                        logger.info(f"Deleted old cache file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Error deleting cache file {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Error processing cache entry {signature}: {e}")
            continue

    return pruned_cache
