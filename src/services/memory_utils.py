"""
Memory management utility functions for the Census app
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from src.clients import load_json_file, save_json_file
from src.domain.memory_persistence_contract import (
    CacheIndexFileV2,
    UserMemoryFileV2,
    migrate_cache_index_file,
    migrate_user_memory_file,
)
from src.domain.strict_json import (
    ConversationMessage,
    JsonMap,
    JsonNest,
    as_json_map,
    as_json_map_optional,
    empty_json_map,
)
from src.state.types import FinalResponseState, WorkflowPlanState
from src.domain.time_utils import is_older_than
from config import RETENTION_DAYS

logger = logging.getLogger(__name__)


def prune_history_by_age(
    history: list[JsonMap] | list[dict[str, JsonNest]], retention_days: int
) -> list[JsonMap]:
    """Remove history entries older than retention_days"""
    if not history:
        return []

    normalized: list[JsonMap] = []
    for row in history:
        if isinstance(row, dict):
            normalized.append(JsonMap.model_validate(row))
        elif isinstance(row, JsonMap):
            normalized.append(row)
        else:
            raise TypeError(f"history entries must be dict or JsonMap, got {type(row)}")

    pruned: list[JsonMap] = []
    for entry in normalized:
        try:
            ts_raw = entry.root.get("timestamp")
            ts_val = ts_raw if isinstance(ts_raw, str) else ""
            if not is_older_than(ts_val, retention_days):
                pruned.append(entry)
        except Exception as e:
            logger.warning(f"Error processing history entry: {e}")
            continue

    return pruned


def prune_cache_by_age(
    entries: JsonMap | dict[str, JsonNest] | None, retention_days: int
) -> JsonMap:
    """Remove cache entries older than retention_days and delete stale files."""
    cleaned = as_json_map(entries)
    if not cleaned.root:
        return empty_json_map()

    pruned: dict[str, JsonNest] = {}
    for signature, metadata in cleaned.root.items():
        meta: dict[str, JsonNest]
        if isinstance(metadata, JsonMap):
            meta = metadata.root
        elif isinstance(metadata, dict):
            meta = metadata
        else:
            logger.warning(f"Skipping non-object cache entry {signature}")
            continue
        try:
            ts_raw = meta.get("timestamp")
            ts_val = ts_raw if isinstance(ts_raw, str) else ""
            if not is_older_than(ts_val, retention_days):
                pruned[signature] = meta
            else:
                fp_raw = meta.get("file_path")
                fp = fp_raw if isinstance(fp_raw, str) else None
                if fp and Path(fp).exists():
                    try:
                        Path(fp).unlink()
                        logger.info(f"Deleted old cache file: {fp}")
                    except OSError as e:
                        logger.warning(f"Error deleting cache file {fp}: {e}")
        except Exception as e:
            logger.warning(f"Error processing cache entry {signature}: {e}")
            continue

    return JsonMap(root=pruned)


def _plan_summary(plan: WorkflowPlanState | None) -> str:
    if plan is None or plan.comparison is None:
        return ""
    cp = plan.comparison
    return (
        f"metric={cp.metric}, dataset={cp.dataset}, years={cp.query_years}, "
        f"comparison_op={cp.comparison_op}"
    )


def build_history_record(
    messages: list[ConversationMessage],
    final: FinalResponseState,
    intent: JsonMap | None,
    geo: JsonMap,
    plan: WorkflowPlanState | None,
    user_id: str,
    *,
    workflow_error: str | None,
) -> JsonMap:
    """Build one typed history snapshot for persisted memory."""

    user_question = messages[-1].content if messages else ""

    geo = as_json_map(geo)
    coerced_intent = as_json_map_optional(intent)
    snapshot_intent = coerced_intent if coerced_intent is not None else empty_json_map()
    plan_summary = _plan_summary(plan)
    rich = bool(final.charts_needed or final.tables_needed)
    answer_type = "visual" if rich else "text"
    success = workflow_error is None

    out = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "user_id": user_id,
        "question": user_question,
        "intent": snapshot_intent.model_dump(mode="python"),
        "geo": geo.model_dump(mode="python"),
        "plan_summary": plan_summary,
        "answer_type": answer_type,
        "success": success,
    }
    return JsonMap.model_validate(out)


def update_profile(
    profile: JsonMap,
    intent: JsonMap | None,
    geo: JsonMap,
    final: FinalResponseState | None,
    *,
    workflow_error: str | None,
) -> JsonMap:
    """Update profile envelope from typed state (returns JsonMap blob for ``UserMemoryFileV2``)."""

    profile = as_json_map(profile)
    geo = as_json_map(geo)
    intent = as_json_map_optional(intent)

    merged = dict(profile.model_dump(mode="python"))

    ok = workflow_error is None

    # Update default geography if this was successful
    if ok and final is not None and geo.root:
        display_raw = geo.root.get("display_name")
        geo_name = display_raw if isinstance(display_raw, str) else ""

        if geo_name:
            merged["default_geo"] = geo.model_dump(mode="python")
            merged["last_geo"] = geo_name

    if ok and intent and intent.root:
        ds_raw = intent.root.get("dataset")
        ds = ds_raw if isinstance(ds_raw, str) else ""

        if ds:
            merged["preferred_dataset"] = ds

    if intent and intent.root.get("measures"):
        ms_raw = intent.root["measures"]
        measure_keys: list[str] = []
        if isinstance(ms_raw, list):
            measure_keys = [str(x) for x in ms_raw]
        elif isinstance(ms_raw, str):
            measure_keys = [ms_raw]

        ali = merged.get("var_aliases")
        if isinstance(ali, dict):
            var_aliases = dict(ali)
        else:
            var_aliases = {}

        for measure in measure_keys:
            if measure not in var_aliases:
                inferred_txt = getattr(final, "answer_text", "") if final else ""
                # Best-effort pattern for Census variable codes in answer text
                m_pat = re.search(r"b\d{6,12}", inferred_txt)
                if m_pat:
                    var_aliases[measure] = m_pat.group(0)

        merged["var_aliases"] = var_aliases

    if "usage_stats" not in merged or merged["usage_stats"] is None:
        merged["usage_stats"] = {
            "total_queries": 0,
            "success_queries": 0,
            "last_query_date": None,
        }

    usage = merged["usage_stats"]
    if isinstance(usage, dict):
        usage.setdefault("total_queries", 0)
        usage.setdefault("success_queries", 0)
        usage["total_queries"] = int(usage.get("total_queries", 0)) + 1
        if ok and final is not None:
            usage["success_queries"] = int(usage.get("success_queries", 0)) + 1
        usage["last_query_date"] = pd.Timestamp.now().isoformat()

    return JsonMap.model_validate(merged)


def enforce_retention_policies(
    profile_file: Path, cache_index_file: Path, user_id: str
) -> None:
    """Enforce retention policies on profile and cache index"""

    try:
        profile_raw = load_json_file(profile_file, {})
        if profile_raw:
            doc = migrate_user_memory_file(dict(profile_raw), fallback_user_id=user_id)
            pruned_history = prune_history_by_age(doc.history, RETENTION_DAYS)
            if len(doc.history) != len(pruned_history):
                logger.info(
                    f"Pruned {len(doc.history) - len(pruned_history)} old history entries"
                )
                doc = doc.model_copy(update={"history": pruned_history})
                save_json_file(profile_file, doc.model_dump())

        raw_cache = load_json_file(cache_index_file, {})
        cache_doc = migrate_cache_index_file(dict(raw_cache))
        flat = cache_doc.entries
        pruned_flat = prune_cache_by_age(flat, RETENTION_DAYS)

        if len(flat.root) != len(pruned_flat.root):
            logger.info(
                f"Pruned {len(flat.root) - len(pruned_flat.root)} old cache entries"
            )
            save_json_file(
                cache_index_file, CacheIndexFileV2(entries=pruned_flat).model_dump()
            )

    except Exception as e:
        logger.error(f"Error enforcing retention policies for user {user_id}: {str(e)}")
