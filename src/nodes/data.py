from typing import Dict, Any, List
from src.state.types import CensusState, QuerySpec
from langchain_core.runnables import RunnableConfig
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import logging

from src.utils.census_api_utils import fetch_census_data
from src.utils.cache_utils import compute_cache_signature, check_cache, save_to_cache
from config import MAX_CONCURRENCY

logger = logging.getLogger(__name__)


def data_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Retrieve and cache Census data"""

    # Get state
    plan = state.get("plan", {})
    cache_index = state.get("cache_index", {})

    if not plan:
        return {
            "error": "No plan found in state",
            "logs": ["data: ERROR - no plan"],
        }
    if not plan.get("queries"):
        return {
            "error": "Plan contains no queries",
            "logs": ["data: ERROR - plan contains no queries"],
        }

    queries = plan["queries"]
    artifacts = state.get("artifacts", {})
    datasets = artifacts.get("datasets", {})
    previews = artifacts.get("previews", {})

    # Add failure tracking
    failures = 0

    # Process queries with concurrency
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        futures = {
            executor.submit(process_single_query, query, cache_index): query
            for query in queries
        }
        for future in as_completed(futures):
            query = futures[future]
            try:
                result = future.result()
                if result["success"]:
                    # Update artifacts
                    datasets[result["save_as"]] = result["file_handle"]
                    previews[result["save_as"]] = result["preview"]
                    # Update cache index
                    cache_index[result["signature"]] = result["cache_entry"]
                else:
                    # Log error
                    logger.error(f"Failed to process query {query}: {result['error']}")
                    failures += 1

            except Exception as e:
                logger.error(f"Exception processing query {query}: {str(e)}")
                failures += 1

    # Check for failures
    if failures > 0:
        return {
            "error": "Some queries failed to process",
            "artifacts": {"datasets": datasets, "previews": previews},
            "cache_index": cache_index,
            "logs": [f"data: processed {len(queries)} queries with some failures"],
        }

    return {
        "artifacts": {
            "datasets": datasets,
            "previews": previews,
        },
        "cache_index": cache_index,
        "logs": [f"data: processed {len(queries)} queries"],
    }


def process_single_query(
    query: QuerySpec, cache_index: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a single query"""

    # Compute cache signature
    signature = compute_cache_signature(
        query["year"], query["dataset"], query["variables"], query["geo"]
    )

    # Check cache first
    cache_entry = check_cache(cache_index, signature)
    if cache_entry:
        return {
            "success": True,
            "save_as": query["save_as"],
            "signature": signature,
            "file_handle": cache_entry["file_path"],
            "preview": load_preview(cache_entry["file_path"]),
            "cache_entry": cache_entry,
        }

    # Fetch from API
    api_result = fetch_census_data(
        query["dataset"], query["year"], query["variables"], query["geo"]
    )

    if not api_result["success"]:
        return {
            "success": False,
            "error": api_result["error"],
        }

    # Save to cache
    cache_entry = save_to_cache(
        api_result["data"],
        signature,
        {
            "year": query["year"],
            "dataset": query["dataset"],
            "variables": query["variables"],
            "geo": query["geo"],
        },
    )

    return {
        "success": True,
        "save_as": query["save_as"],
        "signature": signature,
        "file_handle": cache_entry["file_path"],
        "preview": load_preview(cache_entry["file_path"]),
        "cache_entry": cache_entry,
    }


def load_preview(file_path: str) -> List[List[str]]:
    """Load first 5 rows as preview including header"""

    try:
        df = pd.read_csv(file_path, nrows=5)
        # Include column names as the first row
        preview = [df.columns.tolist()] + df.values.tolist()
        return preview
    except Exception as e:
        logger.error(f"Error loading preview from {file_path}: {str(e)}")
        return []
