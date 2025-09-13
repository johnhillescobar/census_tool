from typing import Dict, Any
from pathlib import Path
import logging

from langchain_core.runnables import RunnableConfig

from src.state.types import CensusState
from src.utils import (
    load_json_file,
    save_json_file,
    prune_history_by_age,
    prune_cache_by_age,
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

    # TODO: Implement memory write node

    return {"logs": ["memory_write: placeholder"]}
