"""
Memory management utility functions for the Census app
"""

import logging
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd

from src.utils.file_utils import load_json_file, save_json_file
from src.utils.time_utils import is_older_than
from config import RETENTION_DAYS

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


def build_history_record(
    messages: List[Dict],
    final: Dict[str, Any],
    intent: Dict[str, Any],
    geo: Dict[str, Any],
    plan: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """Build a history record for a conversation"""

    # Get user question from last message
    user_question = ""
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, dict) and "content" in last_message:
            user_question = last_message["content"]

    # Build plan summary
    plan_summary = ""
    if plan and plan.get("queries"):
        query_count = len(plan["queries"])
        years = [query.get("year", "Unknown") for query in plan["queries"]]
        datasets = [query.get("dataset", "Unknown") for query in plan["queries"]]
        plan_summary = f"{query_count} queries for years {years} using {datasets}"

    return {
        "timestamp": pd.Timestamp.now().isoformat(),
        "user_id": user_id,
        "question": user_question,
        "intent": intent,
        "geo": geo,
        "plan_summary": plan_summary,
        "answer_type": final.get("type", "Unknown"),
        "success": "error" not in final,
    }


def update_profile(
    profile: Dict[str, Any],
    intent: Dict[str, Any],
    geo: Dict[str, Any],
    final: Dict[str, Any],
) -> Dict[str, Any]:
    """Update the profile with new information"""

    updated_profile = profile.copy()

    # Update default geography if this was successful
    if final and "error" not in final and geo:
        geo_name = geo.get("display_name", "Unknown")

        if geo_name:
            updated_profile["default_geo"] = geo
            updated_profile["last_geo"] = geo_name

    # Update preferred dataset if user specific terms
    if final and "error" not in final and intent:
        dataset = intent.get("dataset", "Unknown")

        if dataset:
            updated_profile["preferred_dataset"] = dataset

    # Update var_aliases if they were used
    if intent and intent.get("measures"):
        measures = intent["measures"]
        var_aliases = updated_profile.get("var_aliases", {})

        for measure in measures:
            if measure not in var_aliases:
                # Try to find corresponding variable code from final answer
                if final and "variable" in final:
                    var_aliases[measure] = final["variable"]

        updated_profile["var_aliases"] = var_aliases

    # Update usage statistics
    if "usage_stats" not in updated_profile:
        updated_profile["usage_stats"] = {
            "total_queries": 0,
            "success_queries": 0,
            "last_query_date": None,
        }

    updated_profile["usage_stats"]["total_queries"] += 1
    if final and "error" not in final:
        updated_profile["usage_stats"]["success_queries"] += 1
    updated_profile["usage_stats"]["last_query_date"] = pd.Timestamp.now().isoformat()
    return updated_profile


def enforce_retention_policies(
    profile_file: Path, cache_index_file: Path, user_id: str
):
    """Enforce retention policies on profile and cache index"""

    try:
        # Load current profile and history
        profile = load_json_file(profile_file, {})
        history = profile.get("history", [])

        # Prune history
        pruned_history = prune_history_by_age(history, RETENTION_DAYS)

        if len(history) != len(pruned_history):
            logger.info(
                f"Pruned {len(history) - len(pruned_history)} old history entries"
            )
            profile["history"] = pruned_history
            save_json_file(profile_file, profile)

        # Load and prune cache index
        cache_index = load_json_file(cache_index_file, {})
        pruned_cache_index = prune_cache_by_age(cache_index, RETENTION_DAYS)

        if len(cache_index) != len(pruned_cache_index):
            logger.info(
                f"Pruned {len(cache_index) - len(pruned_cache_index)} old cache entries"
            )
            save_json_file(cache_index_file, pruned_cache_index)

    except Exception as e:
        logger.error(f"Error enforcing retention policies for user {user_id}: {str(e)}")
