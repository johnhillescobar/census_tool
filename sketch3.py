# Great—let's make your app remember everything for 90 days, locally.

# What we'll add

# Thread memory: LangGraph checkpointer (SQLite) so a conversation continues naturally.
# Long-term user memory: JSON files under ./memory with full query history and user profile, pruned to last 90 days.
# Result cache: on-disk cache of fetched Census results, keyed by a stable signature, pruned to last 90 days (and deletes old files).
# Optional semantic recall later (you can re-use Chroma for history if you want, but not required here).
# Drop-in code updates (add to your current script)

# 1. Retention config and helpers
import os
import json
import time
import hashlib
import pandas as pd
import requests
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph.message import add_messages

RETENTION_DAYS = 90
RETENTION_SECONDS = RETENTION_DAYS * 24 * 3600
NOW = lambda: time.time()

MEM_DIR = "./memory"
DATA_DIR = "./data"
os.makedirs(MEM_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def cutoff_ts() -> float:
    return NOW() - RETENTION_SECONDS


def is_fresh(ts: float) -> bool:
    try:
        return float(ts) >= cutoff_ts()
    except Exception:
        return False


def query_signature(q: dict) -> str:
    key = {
        "year": q["year"],
        "dataset": q["dataset"],
        "variables": sorted(q["variables"]),
        "geo": {
            "level": q["geo"]["level"],
            "filters": dict(sorted(q["geo"]["filters"].items())),
        },
    }
    s = json.dumps(key, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# 2. User memory store with 90-day retention


def user_file(user_id: str) -> str:
    return os.path.join(MEM_DIR, f"user{user_id}.json")


def load_user_memory(user_id: str) -> Dict[str, Any]:
    path = user_file(user_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
    else:
        data = {"profile": {"user_id": user_id}, "history": []}
    # prune history older than 90 days
    fresh_hist = [h for h in data.get("history", []) if is_fresh(h.get("timestamp", 0))]
    if len(fresh_hist) != len(data.get("history", [])):
        data["history"] = fresh_hist
        with open(path, "w") as f:
            json.dump(data, f)
    return data


def save_user_memory(user_id: str, profile_update: dict, history_additions: List[dict]):
    # merge and prune, keep full history within 90 days
    data = load_user_memory(user_id)
    data["profile"] = {**(data.get("profile", {})), **(profile_update or {})}
    new_hist = data.get("history", []) + (history_additions or [])
    # prune by time
    new_hist = [h for h in new_hist if is_fresh(h.get("timestamp", 0))]
    data["history"] = new_hist
    with open(user_file(user_id), "w") as f:
        json.dump(data, f)


# 3. Cache index with 90-day retention and file cleanup

CACHE_FILE = os.path.join(MEM_DIR, "cache_index.json")


def load_cache_index() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
    else:
        cache = {}
    # prune old entries and delete old files
    changed = False
    for sig, handle in list(cache.items()):
        ts = handle.get("timestamp", 0)
        if not is_fresh(ts):
            path = handle.get("path")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            cache.pop(sig, None)
            changed = True
    if changed:
        save_cache_index(cache)
    return cache


def save_cache_index(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


# 4. Extend state with profile/history/cache

# Add these fields to your CensusState TypedDict (same reducers as before):
# profile: merge dict
# history: append list
# cache_index: merge dict
# Example:


def merge_dict(old: Optional[dict], new: Optional[dict]) -> dict:
    return {**(old or {}), **(new or {})}


def append_list(old: Optional[list], new: Optional[list]) -> list:
    return (old or []) + (new or [])


class CensusState(TypedDict):
    messages: Annotated[List[Dict[str, Any]], add_messages]
    intent: Annotated[Optional[dict], lambda o, n: n]
    geo: Annotated[Optional[dict], lambda o, n: n]
    candidates: Annotated[Optional[dict], lambda o, n: n]
    plan: Annotated[Optional[dict], lambda o, n: n]
    artifacts: Annotated[dict, merge_dict]
    logs: Annotated[List[str], append_list]
    final: Annotated[Optional[dict], lambda o, n: n]
    error: Annotated[Optional[str], lambda o, n: n]
    profile: Annotated[dict, merge_dict]
    history: Annotated[List[Dict[str, Any]], append_list]
    cache_index: Annotated[dict, merge_dict]


# 5. Memory nodes (load/save with retention)


def memory_load_node(state: CensusState, config) -> Dict[str, Any]:
    user_id = (config.get("configurable", {}) or {}).get("user_id", "anon")
    user_mem = load_user_memory(user_id)
    cache_idx = load_cache_index()
    return {
        "profile": user_mem.get("profile", {}),
        "history": user_mem.get("history", []),  # will be appended into state
        "cache_index": cache_idx,
    }


def memory_write_node(state: CensusState, config) -> Dict[str, Any]:
    user_id = (config.get("configurable", {}) or {}).get("user_id", "anon")
    intent = state.get("intent") or {}
    geo = state.get("geo") or {}
    plan = state.get("plan") or {}
    artifacts = state.get("artifacts", {})
    ds = artifacts.get("datasets", {})
    plan_summary = {
        "n_queries": len(plan.get("queries", [])),
        "years": sorted({q["year"] for q in plan.get("queries", [])})
        if plan.get("queries")
        else [],
        "dataset": plan.get("queries", [{}])[0].get("dataset")
        if plan.get("queries")
        else None,
        "var": plan.get("queries", [{}])[0].get("variables", [None])[0]
        if plan.get("queries")
        else None,
    }
    hist_item = {
        "question": (state.get("messages") or [{}])[-1].get("content", ""),
        "timestamp": NOW(),
        "intent": intent,
        "geo": geo,
        "plan_summary": plan_summary,
        "artifacts_keys": list(ds.keys()),
    }
    # learn preferences
    profile_update = {}
    if geo:
        profile_update["default_geo"] = geo
    if plan_summary.get("dataset"):
        profile_update["preferred_dataset"] = plan_summary["dataset"]
    save_user_memory(user_id, profile_update, [hist_item])
    # persist updated cache index (already pruned on load)
    save_cache_index(state.get("cache_index", {}))
    return {}


# 6. Make the data node cache-aware and timestamp entries


def data_node(state: CensusState) -> Dict[str, Any]:
    plan = state.get("plan") or {}
    queries = plan.get("queries", [])
    cache_index = state.get("cache_index", {})
    datasets, previews = {}, {}
    if not queries:
        return {"error": "No queries to run"}

    for q in queries:
        sig = query_signature(q)
        # cache hit
        if sig in cache_index:
            h = cache_index[sig]
            # refresh timestamp so it stays within retention
            h["timestamp"] = NOW()
            datasets[q["save_as"]] = h
            try:
                df = pd.read_csv(h["path"])
                previews[q["save_as"]] = df.head(5).to_dict(orient="records")
            except Exception:
                pass
            continue

        # fetch
        url = build_census_url(q["year"], q["dataset"], q["variables"], q["geo"])
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        raw = r.json()
        cols, rows = raw[0], raw[1:]
        df = pd.DataFrame(rows, columns=cols)
        df["year"] = q["year"]
        path = os.path.join(DATA_DIR, f"{q['save_as']}.csv")
        df.to_csv(path, index=False)
        handle = {
            "path": path,
            "n_rows": len(df),
            "n_cols": len(df.columns),
            "year": q["year"],
            "dataset": q["dataset"],
            "timestamp": NOW(),
        }
        datasets[q["save_as"]] = handle
        previews[q["save_as"]] = df.head(5).to_dict(orient="records")
        cache_index[sig] = handle

    return {
        "artifacts": {"datasets": datasets, "previews": previews},
        "cache_index": cache_index,
    }


# 7) Wire memory nodes and checkpointer

from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver("checkpoints.db")

# builder.add_node("memory_load", memory_load_node)
# builder.add_node("memory_write", memory_write_node)

# builder.add_edge(START, "memory_load")
# builder.add_edge("memory_load", "intent")

# ... your existing edges ...
# builder.add_edge("answer", "memory_write")
# builder.add_edge("memory_write", END)

# graph = builder.compile(checkpointer=checkpointer)

# 8. Invoke with user_id and thread_id

user_id = "alice123"
thread_id = f"{user_id}-default"

init_state: CensusState = {
    "messages": [
        {"role": "user", "content": "Hispanics income from 2012 to 2023 in NYC"}
    ],
    "artifacts": {"datasets": {}, "previews": {}},
    "logs": [],
    "profile": {},
    "history": [],
    "cache_index": {},
}
# out = graph.invoke(
#     init_state,
#     config={"configurable": {"user_id": user_id, "thread_id": thread_id}}
# )
# print(out.get("final"))

# Practical notes

# Full history within 90 days: Each completed question adds a full history record (question, intent, geo, plan summary, artifact keys) with a timestamp. On load/save we prune anything older than 90 days.
# Result cache retention: We remove cache entries and delete their files when older than 90 days. Hits refresh the timestamp so frequently used results persist.
# Disk layout:
# ./memory/user_{user_id}.json: profile + history
# ./memory/cache_index.json: query signature -> file handle
# ./data/*.csv: fetched datasets (removed automatically when their cache entries age out)
# checkpoints.db: conversation checkpoints (thread memory)
# Thread memory: pass the same thread_id on each turn to continue the conversation. If you want to clear a thread, change thread_id.
# Optional summarizer: If you prefer to keep the prompt small, you can still add the summarizer node; it won't affect the 90-day long-term history, which is stored separately.
# Running local: Everything persists to local files. You can back up ./memory and ./data if needed.
# If you want, I can fold these pieces into a single consolidated script with your Chroma retrieval already wired in and tested against a couple of example queries.


# Note: This file requires additional imports and dependencies from the main sketch.py file
# such as build_census_url function, etc.
