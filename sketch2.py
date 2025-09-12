# Conversation memory: past turns so the user can say "same geo as before" and it works.
# User profile/preferences: default geo (NYC), preferred dataset (ACS 5-year), typical year range, preferred summary level.
# Result cache: reuse previously fetched Census data instead of calling the API again.
# Query history: list of prior questions with the variables, years, and files produced.
# Semantic memory: recall similar past questions to guide new plans.
# I'll propose a sensible default that includes all five, and you can tell me what to keep/remove.

# What we'll add

# Thread memory (conversation): use LangGraph's checkpointer so a session/thread's full state persists.
# User memory (across threads): simple JSON files (or a DB) keyed by user_id for profile + history.
# Result cache: a small on-disk index keyed by query signature; the data node will reuse cached files.
# Optional semantic memory: a Chroma collection for "user_history" so we can pull similar past queries.
# Minimal changes to your graph

# New state fields and reducers
# Add these keys:
# profile: dict of user prefs (merge dict)
# history: list of past queries (append)
# cache_index: dict of query_signature -> dataset handle (merge dict)
# summary: a short text summary of long message history (overwrite)
# Keep messages append, artifacts merge, others overwrite.
# 2. Use a checkpointer (thread-level memory)

# Persist every step. You'll invoke with a thread_id to resume later.
# 3. Memory nodes

# memory_load: load user profile/history/cache into state at start (based on user_id).
# memory_write: after answer, update user profile, append history, update cache_index on disk.
# 4. Tiny message summarizer (optional)

# If messages grows too big, keep a short summary and truncate older turns.
# Code sketch (add/replace in your current script)

# A) Extend the state

from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
import json
import os
import time
import hashlib
import pandas as pd
import requests


def merge_dict(old: Optional[dict], new: Optional[dict]) -> dict:
    return {**(old or {}), **(new or {})}


def append_list(old: Optional[list], new: Optional[list]) -> list:
    return (old or []) + (new or [])


class QueryHistory(TypedDict, total=False):
    question: str
    timestamp: float
    intent: dict
    geo: dict
    plan_summary: dict  # e.g., {"n_queries": 12, "years":[2012,2023], "dataset":"acs/acs5", "var":"B19013I_001E"}
    artifacts_keys: List[str]  # save_as keys produced


class Profile(TypedDict, total=False):
    user_id: str
    default_geo: dict  # same shape as Geo
    preferred_dataset: str  # e.g., "acs/acs5"
    default_year_range: dict  # {"start_year": 2012, "end_year": 2023}
    preferred_level: str  # "place" | "county" | ...
    var_aliases: Dict[
        str, str
    ]  # e.g., {"population":"B01003_001E","median_income_hispanic":"B19013I_001E"}


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
    # new
    profile: Annotated[dict, merge_dict]
    history: Annotated[List[QueryHistory], append_list]
    cache_index: Annotated[dict, merge_dict]
    summary: Annotated[Optional[str], lambda o, n: n]


# B) Persist threads with a checkpointer

from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver("checkpoints.db")
# graph = builder.compile(checkpointer=checkpointer)

# When you run:
# out = graph.invoke(init_state, config={"configurable": {"thread_id": f"{user_id}-thread"}})
# Later calls with the same thread_id resume state automatically.

# C) Simple user memory store (JSON files)

MEM_DIR = "./memory"
os.makedirs(MEM_DIR, exist_ok=True)
CACHE_FILE = os.path.join(MEM_DIR, "cache_index.json")


def user_file(user_id: str) -> str:
    return os.path.join(MEM_DIR, f"user{user_id}.json")


def load_user_memory(user_id: str) -> Dict[str, Any]:
    path = user_file(user_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"profile": {"user_id": user_id}, "history": []}


def save_user_memory(
    user_id: str, profile: dict, history_additions: List[QueryHistory]
):
    data = load_user_memory(user_id)
    data["profile"] = {**(data.get("profile", {})), **(profile or {})}
    data["history"] = (data.get("history", []) + (history_additions or []))[
        -200:
    ]  # keep last 200
    with open(user_file(user_id), "w") as f:
        json.dump(data, f)


def load_cache_index() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache_index(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


# D) Memory nodes (they can accept config to read user_id)


def memory_load_node(state: CensusState, config) -> Dict[str, Any]:
    user_id = (config.get("configurable", {}) or {}).get("user_id", "anon")
    user_mem = load_user_memory(user_id)
    cache_idx = load_cache_index()
    # Optional: prefill defaults if empty
    profile = user_mem.get("profile", {})
    return {
        "profile": profile,
        "history": user_mem.get("history", []),
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
    hist_item: QueryHistory = {
        "question": (state.get("messages") or [{}])[-1].get("content", ""),
        "timestamp": time.time(),
        "intent": intent,
        "geo": geo,
        "plan_summary": plan_summary,
        "artifacts_keys": list(ds.keys()),
    }
    # Update profile heuristically (learn last geo, dataset, and var alias)
    profile_update = {}
    if geo:
        profile_update["default_geo"] = geo
    if plan_summary.get("dataset"):
        profile_update["preferred_dataset"] = plan_summary["dataset"]
    # Example: map measure to var for future reuse
    measures = " ".join(intent.get("measures", []))
    if plan_summary.get("var") and measures:
        va = (state.get("profile", {}).get("var_aliases", {})).copy()
        va[measures] = plan_summary["var"]
        profile_update["var_aliases"] = va
    save_user_memory(user_id, profile_update, [hist_item])
    # Persist cache index if it changed
    save_cache_index(state.get("cache_index", {}))
    return {}


# E) Plug memory nodes into the graph

# builder.add_node("memory_load", memory_load_node)
# builder.add_node("memory_write", memory_write_node)

# builder.add_edge(START, "memory_load")
# builder.add_edge("memory_load", "intent")   # then your existing flow

# ...
# builder.add_edge("answer", "memory_write")
# builder.add_edge("memory_write", END)

# F) Make data_node cache-aware

# Compute a stable signature for each query.
# If signature exists in cache_index, reuse the saved file.
# Otherwise fetch, save, and record in cache_index and artifacts.


def query_signature(q: dict) -> str:
    # Stable, order-independent signature
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


def data_node(state: CensusState) -> Dict[str, Any]:
    plan = state.get("plan") or {}
    queries = plan.get("queries", [])
    cache_index = state.get("cache_index", {})
    datasets, previews = {}, {}
    for q in queries:
        sig = query_signature(q)
        if sig in cache_index:
            h = cache_index[sig]
            datasets[q["save_as"]] = h
            try:
                df = pd.read_csv(h["path"])
                previews[q["save_as"]] = df.head(5).to_dict(orient="records")
            except Exception:
                pass
            continue
        # Not cached: fetch
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
        }
        datasets[q["save_as"]] = handle
        previews[q["save_as"]] = df.head(5).to_dict(orient="records")
        cache_index[sig] = handle
    return {
        "artifacts": {"datasets": datasets, "previews": previews},
        "cache_index": cache_index,
    }


# G) Optional: message summarizer to control prompt length

MAX_TURNS = 20


def summarize_messages(messages: List[dict]) -> str:
    # Simple heuristic; replace with an LLM if you want
    user_utts = [m["content"] for m in messages if m.get("role") == "user"][-5:]
    return "Summary: previous user asked about " + "; ".join(user_utts)


def summarizer_node(state: CensusState) -> Dict[str, Any]:
    msgs = state.get("messages", [])
    if len(msgs) <= MAX_TURNS:
        return {}
    summary = summarize_messages(msgs)
    # Keep only last few turns to save tokens
    trimmed = msgs[-8:]
    return {"summary": summary, "messages": trimmed, "logs": ["messages summarized"]}


# Add it early in your flow (e.g., after memory_load or after intent) if needed:

# builder.add_node("summarize", summarizer_node)
# builder.add_edge("memory_load", "summarize")
# builder.add_edge("summarize", "intent")

# H) Optional semantic memory in Chroma

# Create a "user_history" collection.
# After each answer, upsert a document: question + plan summary + geo + years. Metadata includes user_id and artifacts handles.
# Before retrieval, query this collection with the current question to recall similar past work (e.g., reuse var_aliases or years).

# Why this setup works

# Thread-level memory means users can continue a conversation naturally.
# User-level memory means "use the same geo as before" works across new sessions.
# Cache makes repeated questions fast and cheap (no duplicate API calls).
# History gives you an audit trail and enables semantic recall later.


# Note: This file requires additional imports and dependencies from the main sketch.py file
# such as DATA_DIR, build_census_url function, etc.
