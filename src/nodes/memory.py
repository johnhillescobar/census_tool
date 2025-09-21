from typing import Dict, Any
from pathlib import Path
import pandas as pd
import logging

from langchain_core.runnables import RunnableConfig

from src.state.types import CensusState
from src.utils import (
    load_json_file,
    save_json_file,
    prune_history_by_age,
    prune_cache_by_age,
    build_history_record,
    update_profile,
    enforce_retention_policies,
)

from config import RETENTION_DAYS

logger = logging.getLogger(__name__)


def memory_load_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Load user profile, history, and cache index"""

    # Get user_id from config
    user_id = config.get("user_id")

    if not user_id:
        logger.error("User ID is required")
        return {
            "error": "user_id is required in config",
            "logs": ["memory_load: ERROR - user_id missing"],
        }

    logger.info(f"Loading user memory for user_id: {user_id}")

    # Initialize user memory
    memory_dir = Path("memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Load user profile and history
    profile_file = memory_dir / f"user_{user_id}.json"
    profile = load_json_file(profile_file, {})

    # Initialize profile with defaults if empty
    if not profile:
        profile = {
            "user_id": user_id,
            "default_geo": {},
            "preferred_dataset": "acs/acs5",
            "default_year_range": [2012, 2023],
            "preferred_level": "place",
            "var_aliases": {},
        }

    # Load and prune history
    history = profile.get("history", [])
    pruned_history = prune_history_by_age(history, RETENTION_DAYS)

    if len(history) != len(pruned_history):
        logger.info(f"Pruned {len(history) - len(pruned_history)} old history items")
        profile["history"] = pruned_history
        save_json_file(profile_file, profile)

    # Load and prune cache index
    cache_index_file = memory_dir / f"cache_index_{user_id}.json"
    cache_index = load_json_file(cache_index_file, {})
    pruned_cache_index = prune_cache_by_age(cache_index, RETENTION_DAYS)

    if len(cache_index) != len(pruned_cache_index):
        logger.info(
            f"Pruned {len(cache_index) - len(pruned_cache_index)} old cache items"
        )
        save_json_file(cache_index_file, pruned_cache_index)

    log_entry = f"memory_load: loaded profile for user_{user_id}, {len(pruned_history)} history entries, {len(pruned_cache_index)} cache entries"

    return {
        "profile": profile,
        "history": pruned_history,
        "cache_index": pruned_cache_index,
        "logs": [log_entry],
    }


def memory_write_node(state: CensusState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Write user profile, history, and cache index"""

    # Get user_id from config
    user_id = config.get("user_id")

    if not user_id:
        logger.error("User ID is required")
        return {
            "error": "user_id is required in config",
            "logs": ["memory_write: ERROR - user_id missing"],
        }

    logger.info(f"Writing user memory for user_id: {user_id}")

    # Get profile and history from state
    profile = state.get("profile", {})
    history = state.get("history", [])
    cache_index = state.get("cache_index", {})
    messages = state.get("messages", [])
    intent = state.get("intent", {})
    geo = state.get("geo", {})
    plan = state.get("plan", {})
    final = state.get("final", {})

    # Initialize memory directory
    memory_dir = Path("memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Build history record for this conversation
        if messages and final:
            history_record = build_history_record(
                messages, final, intent, geo, plan, user_id
            )
            history.append(history_record)

        # 2. Update profile with latest intent and geo
        updated_profile = update_profile(profile, intent, geo, final)

        # 3. Save profile and history
        profile_file = memory_dir / f"user_{user_id}.json"
        updated_profile["history"] = history
        updated_profile["user_id"] = user_id
        updated_profile["last_updated"] = pd.Timestamp.now().isoformat()

        save_success = save_json_file(profile_file, updated_profile)
        if not save_success:
            logger.error(f"Failed to save profile for user_{user_id}")
            return {
                "error": "failed to save profile",
                "logs": ["memory_write: ERROR - failed to save profile"],
            }

        # 4. Save cache index
        cache_index_file = memory_dir / f"cache_index_{user_id}.json"
        cache_success = save_json_file(cache_index_file, cache_index)
        if not cache_success:
            logger.error(f"Failed to save cache index for user_{user_id}")
            return {
                "error": "failed to save cache index",
                "logs": ["memory_write: ERROR - failed to save cache index"],
            }

        # 5. Enforcce retention policies
        enforce_retention_policies(profile_file, cache_index_file, user_id)

        log_entry = f"memory_write: saved profile and {len(history)} history entries for user_{user_id}"

        return {
            "profile": updated_profile,
            "history": history,
            "cache_index": cache_index,
            "logs": [log_entry],
        }

    except Exception as e:
        logger.error(f"Error writing memory for user {user_id}: {str(e)}")
        return {
            "error": f"Error writing memory: {str(e)}",
            "logs": [f"memory_write: ERROR - {str(e)}"],
        }
