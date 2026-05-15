from pathlib import Path
import logging

import pandas as pd
from langchain_core.runnables import RunnableConfig

from src.state.types import CensusState
from src.clients import load_json_file, save_json_file
from src.domain.memory_persistence_contract import (
    CacheIndexFileV2,
    UserMemoryFileV2,
    cache_index_for_state,
    memory_profile_to_state_profile,
    migrate_cache_index_file,
    migrate_user_memory_file,
)
from src.domain.strict_json import JsonMap, as_json_map, as_json_map_optional
from src.services import (
    prune_history_by_age,
    prune_cache_by_age,
    build_history_record,
    update_profile,
    enforce_retention_policies,
)
from src.workflows.graph_patch import CensusGraphPatch

from config import RETENTION_DAYS

logger = logging.getLogger(__name__)


def memory_load_node(state: CensusState, config: RunnableConfig) -> dict[str, object]:
    """Load user profile, history, and cache index"""

    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        logger.error("User ID is required")
        return CensusGraphPatch(
            error="user_id is required in config",
            logs=["memory_load: ERROR - user_id missing"],
        ).as_langgraph_update()

    logger.info(f"Loading user memory for user_id: {user_id}")

    memory_dir = Path("memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    profile_file = memory_dir / f"user_{user_id}.json"
    raw_profile = load_json_file(profile_file, {})

    if not raw_profile:
        doc = UserMemoryFileV2(
            user_id=user_id,
            default_geo=JsonMap.model_validate({}),
        )
    else:
        doc = migrate_user_memory_file(dict(raw_profile), fallback_user_id=user_id)

    pruned_history = prune_history_by_age(doc.history, RETENTION_DAYS)

    if len(doc.history) != len(pruned_history):
        logger.info(f"Pruned {len(doc.history) - len(pruned_history)} old history items")
        doc = doc.model_copy(update={"history": pruned_history})
        save_json_file(profile_file, doc.model_dump())

    cache_index_file = memory_dir / f"cache_index_{user_id}.json"
    raw_cache = load_json_file(cache_index_file, {})
    cache_doc = migrate_cache_index_file(dict(raw_cache))
    pruned_entries = prune_cache_by_age(cache_doc.entries, RETENTION_DAYS)

    if len(cache_doc.entries.root) != len(pruned_entries.root):
        logger.info(
            f"Pruned {len(cache_doc.entries.root) - len(pruned_entries.root)} old cache items"
        )
        save_json_file(
            cache_index_file,
            CacheIndexFileV2(entries=pruned_entries).model_dump(),
        )

    log_entry = (
        f"memory_load: loaded profile for user_{user_id}, {len(pruned_history)} "
        f"history entries, {len(pruned_entries.root)} cache entries"
    )

    return CensusGraphPatch(
        profile=memory_profile_to_state_profile(doc),
        history=pruned_history,
        cache_index=pruned_entries,
        logs=[log_entry],
    ).as_langgraph_update()


def memory_write_node(state: CensusState, config: RunnableConfig) -> dict[str, object]:
    """Write user profile, history, and cache index"""

    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        logger.error("User ID is required")
        return CensusGraphPatch(
            error="user_id is required in config",
            logs=["memory_write: ERROR - user_id missing"],
        ).as_langgraph_update()

    logger.info(f"Writing user memory for user_id: {user_id}")

    doc = migrate_user_memory_file(
        as_json_map(state.profile).model_dump(mode="python"), fallback_user_id=user_id
    )

    history = list(state.history)
    messages = state.messages
    intent = as_json_map_optional(state.intent)
    geo = as_json_map(state.geo)
    plan = state.plan
    final = state.final

    memory_dir = Path("memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    try:
        if messages and final:
            history_record = build_history_record(
                messages,
                final,
                intent,
                geo,
                plan,
                user_id,
                workflow_error=state.error,
            )
            history.append(history_record)

        profile_as_map = JsonMap.model_validate(doc.model_dump(mode="python"))
        updated_profile_map = update_profile(
            profile_as_map,
            intent,
            geo,
            final,
            workflow_error=state.error,
        )
        payload = updated_profile_map.model_dump(mode="python")
        payload["history"] = [h.model_dump(mode="python") for h in history]
        payload["user_id"] = user_id
        payload["last_updated"] = pd.Timestamp.now().isoformat()

        profile_out = UserMemoryFileV2.model_validate(payload)
        profile_file = memory_dir / f"user_{user_id}.json"

        save_success = save_json_file(profile_file, profile_out.model_dump())
        if not save_success:
            logger.error(f"Failed to save profile for user_{user_id}")
            return CensusGraphPatch(
                error="failed to save profile",
                logs=["memory_write: ERROR - failed to save profile"],
            ).as_langgraph_update()

        cache_doc_out = CacheIndexFileV2(entries=as_json_map(state.cache_index))
        cache_index_file = memory_dir / f"cache_index_{user_id}.json"
        cache_success = save_json_file(cache_index_file, cache_doc_out.model_dump())
        if not cache_success:
            logger.error(f"Failed to save cache index for user_{user_id}")
            return CensusGraphPatch(
                error="failed to save cache index",
                logs=["memory_write: ERROR - failed to save cache index"],
            ).as_langgraph_update()

        enforce_retention_policies(profile_file, cache_index_file, user_id)

        log_entry = f"memory_write: saved profile and {len(history)} history entries for user_{user_id}"

        return CensusGraphPatch(
            profile=memory_profile_to_state_profile(profile_out),
            cache_index=cache_index_for_state(cache_doc_out),
            logs=[log_entry],
        ).as_langgraph_update()

    except Exception as e:
        logger.error(f"Error writing memory for user {user_id}: {str(e)}")
        return CensusGraphPatch(
            error=f"Error writing memory: {str(e)}",
            logs=[f"memory_write: ERROR - {str(e)}"],
        ).as_langgraph_update()
