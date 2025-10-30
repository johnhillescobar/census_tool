from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd
import json
import hashlib
import time
import os


def compute_cache_signature(
    year: int, dataset: str, variables: List[str], geo: Dict[str, Any]
) -> str:
    """Compute a stable signature for the cache key"""

    # Sort variables for consistent ordering
    sorted_vars = sorted(variables)

    # Create a stable string representation
    cache_data = {
        "year": year,
        "dataset": dataset,
        "variables": sorted_vars,
        "geo": geo,
    }

    # Convert to JSON string and hash
    cache_str = json.dumps(cache_data, sort_keys=True)
    return hashlib.md5(cache_str.encode()).hexdigest()


def check_cache(
    cache_index: Dict[str, Any], signature: str
) -> Optional[Dict[str, Any]]:
    """Check if data exists in cache and still valid"""
    if signature not in cache_index:
        return None

    cache_entry = cache_index[signature]
    file_path = cache_entry.get("file_path")

    # Check if file still exists
    if not os.path.exists(file_path):
        return None

    # Return cache entry with refreshed timestamp
    cache_entry["timestamp"] = time.time()
    return cache_entry


def save_to_cache(
    data: List[List[str]], signature: str, metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Save data to cache and return a cache entry"""

    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    # Save as CSV
    df = pd.DataFrame(data[1:], columns=data[0])
    file_path = data_dir / f"{signature}.csv"
    df.to_csv(file_path, index=False)

    # Create cache entry
    cache_entry = {
        "file_path": str(file_path),
        "timestamp": time.time(),
        "metadata": metadata,
        "signature": signature,
    }
    return cache_entry
