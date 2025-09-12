# Awesome—let’s get you a concrete template you can run and then tailor. I’ll assume:

# Python
# LangGraph
# Pandas
# Vector DB: FAISS (easy local default; you can swap for Chroma, Pinecone, etc.)
# File storage: local ./data
# If you use a different vector DB or storage, tell me and I’ll swap the stubs.

# Code sketch (single file style, with TODOs where you’ll plug in your pieces)

from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any
from typing import cast
from typing_extensions import NotRequired
import os, json, time, requests
import pandas as pd
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


# --------------------------
# Reducers (merge rules)
# --------------------------
def merge_dict(old: Optional[dict], new: Optional[dict]) -> dict:
    return {**(old or {}), **(new or {})}


def append_list(old: Optional[list], new: Optional[list]) -> list:
    return (old or []) + (new or [])


# --------------------------
# State schema
# --------------------------
class Intent(TypedDict, total=False):
    is_census: bool
    answer_type: Literal["single", "series", "table"]
    measures: List[str]  # e.g., ["population"] or ["median_income", "hispanic"]
    time: Dict[str, int]  # {"year": 2023} or {"start_year": 2012, "end_year": 2023}
    geo_hint: str  # e.g., "NYC", "New York City"
    needs_clarification: bool


class Geo(TypedDict, total=False):
    level: Literal[
        "state", "county", "place", "tract", "block group", "nation", "metro area"
    ]
    filters: Dict[str, str]  # e.g., {"state": "36", "place": "51000"}
    note: NotRequired[str]


class CandidateVar(TypedDict, total=False):
    var: str
    label: str
    concept: str
    dataset: str  # e.g., "acs/acs5"
    years_available: List[int]
    score: float


class Candidates(TypedDict, total=False):
    variables: List[CandidateVar]
    years: List[int]
    notes: NotRequired[str]


class QuerySpec(TypedDict, total=False):
    year: int
    dataset: str
    variables: List[str]  # ["B01003_001E","NAME"]
    geo: Geo
    save_as: str  # artifact key


class Plan(TypedDict, total=False):
    queries: List[QuerySpec]
    needs_agg: bool
    agg_spec: NotRequired[Dict[str, Any]]


class DatasetHandle(TypedDict, total=False):
    path: str
    n_rows: int
    n_cols: int
    year: int
    dataset: str


class Artifacts(TypedDict, total=False):
    datasets: Dict[str, DatasetHandle]  # key: save_as
    previews: Dict[str, List[Dict[str, Any]]]


class Final(TypedDict, total=False):
    answer_text: str
    table_path: NotRequired[str]
    preview: NotRequired[List[Dict[str, Any]]]


class CensusState(TypedDict):
    messages: Annotated[List[Dict[str, Any]], add_messages]  # chat turns
    intent: Annotated[Optional[Intent], lambda o, n: n]  # overwrite
    geo: Annotated[Optional[Geo], lambda o, n: n]  # overwrite
    candidates: Annotated[Optional[Candidates], lambda o, n: n]  # overwrite
    plan: Annotated[Optional[Plan], lambda o, n: n]  # overwrite
    artifacts: Annotated[Artifacts, merge_dict]  # merge dict
    logs: Annotated[List[str], append_list]  # append list
    final: Annotated[Optional[Final], lambda o, n: n]  # overwrite
    error: Annotated[Optional[str], lambda o, n: n]  # overwrite


# --------------------------
# Config and helpers
# --------------------------
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)


def log(state: CensusState, msg: str) -> Dict[str, Any]:
    return {"logs": [f"{time.strftime('%X')} {msg}"]}


def safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# Minimal geo resolver for NYC (expand for your needs)
NYC = {"state": "36", "place": "51000"}
NYC_COUNTIES = [
    "005",
    "047",
    "061",
    "081",
    "085",
]  # Bronx, Kings, New York, Queens, Richmond


def resolve_geo_hint(geo_hint: str) -> Geo:
    text = (geo_hint or "").strip().lower()
    if text in ("nyc", "new york city", "ny city", "nyc, ny"):
        return {
            "level": "place",
            "filters": {"state": "36", "place": "51000"},
            "note": "NYC place",
        }
    # TODO: add more resolvers: state names, counties, tracts via geocoder or lookup
    return {"level": "place", "filters": NYC, "note": "defaulted to NYC"}


def build_census_url(year: int, dataset: str, variables: List[str], geo: Geo) -> str:
    base = f"https://api.census.gov/data/{year}/{dataset}"
    get_vars = ",".join(variables)
    level = geo["level"]
    filters = geo["filters"]
    # Build for/in params
    if level == "place":
        for_part = f"place:{filters['place']}"
        in_part = f"in=state:{filters['state']}"
    elif level == "county":
        for_part = (
            f"county:" if "county" not in filters else f"county:{filters['county']}"
        )
        in_part = f"in=state:{filters['state']}"
    elif level == "state":
        for_part = f"state:{filters.get('state', '')}"
        in_part = ""
    else:
        # TODO: implement other levels (tract, block group) with for=tract:&in=state:..&in=county:..
        for_part = "state:"
        in_part = ""
    params = f"?get={get_vars}&for={for_part}"
    if in_part:
        params += f"&{in_part}"
    return base + params


# --------------------------
# Vector index stubs
# --------------------------
# Replace with your actual index (FAISS/Chroma/etc.)
class VarIndex:
    # Minimal interface
    def similarity_search(self, query: str, k: int) -> List[Dict[str, Any]]:
        # Return docs with .metadata containing var, label, dataset, years_available, concept
        return []


def load_var_index() -> VarIndex:
    # TODO: load or build your variable index from the Census Variables API
    # For now, return a stub; see notes below on building this.
    return VarIndex()


# --------------------------
# Nodes
# --------------------------
def intent_node(state: CensusState) -> Dict[str, Any]:
    # Simple heuristic; swap with an LLM for better results
    user = safe_get(state, "messages", -1, "content", default="") or ""
    text = user.lower()
    is_census = any(
        w in text
        for w in ["census", "population", "income", "acs", "median", "tract", "county"]
    )
    # Decide answer_type
    answer_type: Literal["single", "series", "table"] = "single"
    if any(w in text for w in ["from", "to", "over time", "trend", "by year", "years"]):
        answer_type = "series"
    if any(
        w in text for w in ["by county", "by tract", "breakdown", "table", "across"]
    ):
        answer_type = "table"
    # Measures guess
    measures = []
    if "population" in text:
        measures.append("population")
    if "income" in text or "median income" in text:
        measures.append("median_income")
    if "hispanic" in text or "latino" in text:
        measures.append("hispanic")
    # Time guess
    time: Dict[str, int] = {}
    # naive year extraction
    import re

    years = [int(y) for y in re.findall(r"\b(20[01]\d|202[0-9]|199[0-9])\b", text)]
    if len(years) == 1:
        time = {"year": years[0]}
    elif len(years) >= 2:
        time = {"start_year": min(years), "end_year": max(years)}
    # Geo hint
    geo_hint = "nyc" if "nyc" in text or "new york city" in text else user
    intent: Intent = {
        "is_census": bool(is_census),
        "answer_type": answer_type,
        "measures": measures or ["population"],
        "time": time or {"year": 2023},
        "geo_hint": geo_hint,
        "needs_clarification": False,
    }
    return {"intent": intent} | log(state, f"Intent: {intent}")


def geo_node(state: CensusState) -> Dict[str, Any]:
    intent = cast(Intent, state.get("intent") or {})
    geo = resolve_geo_hint(intent.get("geo_hint", ""))
    return {"geo": geo} | log(state, f"Geo resolved: {geo}")


def retrieve_node(state: CensusState) -> Dict[str, Any]:
    intent = cast(Intent, state.get("intent") or {})
    measures = " ".join(intent.get("measures", []))
    time = intent.get("time", {})
    yr_hint = []
    if "year" in time:
        yr_hint = [time["year"]]
    if "start_year" in time and "end_year" in time:
        yr_hint = list(range(time["start_year"], time["end_year"] + 1))
    idx = load_var_index()
    # Query examples: "population total", "median income hispanic ACS"
    q = f"{measures} census acs variables"
    docs = idx.similarity_search(q, k=10)  # TODO: implement for your vector DB
    variables: List[CandidateVar] = []
    for d in docs:
        md = d.get("metadata", {})
        variables.append(
            {
                "var": md.get("var"),
                "label": md.get("label"),
                "concept": md.get("concept", ""),
                "dataset": md.get("dataset", "acs/acs5"),
                "years_available": md.get("years_available", []),
                "score": d.get("score", 0.0),
            }
        )
    # Fallback examples if index not set
    if not variables and "population" in measures:
        variables = [
            {
                "var": "B01003_001E",
                "label": "Total population",
                "concept": "TOTAL POPULATION",
                "dataset": "acs/acs5",
                "years_available": list(range(2010, 2024)),
                "score": 0.99,
            }
        ]
    if not variables and "median_income" in measures and "hispanic" in measures:
        variables = [
            {
                "var": "B19013I_001E",
                "label": "Median household income in the past 12 months (Hispanic or Latino Householder)",
                "concept": "INCOME IN THE PAST 12 MONTHS (IN 2023 INFLATION-ADJUSTED DOLLARS)",
                "dataset": "acs/acs5",
                "years_available": list(range(2010, 2024)),
                "score": 0.98,
            }
        ]
    years = yr_hint or (variables[0]["years_available"] if variables else [])
    cand: Candidates = {"variables": variables, "years": years}
    return {"candidates": cand} | log(
        state, f"Retrieved {len(variables)} variable candidates"
    )


def plan_node(state: CensusState) -> Dict[str, Any]:
    intent = cast(Intent, state.get("intent") or {})
    geo = cast(Geo, state.get("geo") or {})
    cand = cast(Candidates, state.get("candidates") or {})
    vars_ = cand.get("variables", [])
    if not vars_:
        return {"error": "No variables found", "plan": None} | log(
            state, "Planning failed: no variables"
        )
    primary = vars_[0]  # pick best match
    # Years to query
    years: List[int]
    t = intent.get("time", {})
    if "year" in t:
        years = [t["year"]]
    elif "start_year" in t and "end_year" in t:
        years = [
            y
            for y in range(t["start_year"], t["end_year"] + 1)
            if y in set(primary["years_available"])
        ]
    else:
        years = (
            [max(primary["years_available"])] if primary.get("years_available") else []
        )
    # Build queries
    queries: List[QuerySpec] = []
    for y in years:
        queries.append(
            {
                "year": y,
                "dataset": primary["dataset"],
                "variables": [primary["var"], "NAME"],
                "geo": geo,
                "save_as": f"{primary['var']}{geo['level']}{y}",
            }
        )
    plan: Plan = {"queries": queries, "needs_agg": False}
    return {"plan": plan} | log(state, f"Plan with {len(queries)} queries")


def data_node(state: CensusState) -> Dict[str, Any]:
    plan = cast(Plan, state.get("plan") or {})
    queries = plan.get("queries", [])
    if not queries:
        return {"error": "No queries to run"} | log(state, "No queries to run")
    datasets: Dict[str, DatasetHandle] = {}
    previews: Dict[str, List[Dict[str, Any]]] = {}
    for q in queries:
        url = build_census_url(q["year"], q["dataset"], q["variables"], q["geo"])
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            raw = r.json()
            # First row is header
            cols = raw[0]
            rows = raw[1:]
            df = pd.DataFrame(rows, columns=cols)
            df["year"] = q["year"]
            save_name = f"{q['save_as']}.csv"
            path = os.path.join(DATA_DIR, save_name)
            df.to_csv(path, index=False)
            datasets[q["save_as"]] = {
                "path": path,
                "n_rows": len(df),
                "n_cols": len(df.columns),
                "year": q["year"],
                "dataset": q["dataset"],
            }
            previews[q["save_as"]] = df.head(5).to_dict(orient="records")
        except Exception as e:
            return {"error": f"API error for {url}: {e}"} | log(
                state, f"API error: {e}"
            )
    artifacts: Artifacts = {"datasets": datasets, "previews": previews}
    return {"artifacts": artifacts} | log(state, f"Fetched {len(datasets)} datasets")


def answer_node(state: CensusState) -> Dict[str, Any]:
    intent = cast(Intent, state.get("intent") or {})
    artifacts = cast(
        Artifacts, state.get("artifacts") or {"datasets": {}, "previews": {}}
    )
    answer_type = intent.get("answer_type", "single")
    datasets = artifacts.get("datasets", {})
    if not datasets:
        txt = "I couldn't retrieve Census data for this query."
        return {
            "final": {"answer_text": txt},
            "messages": [{"role": "assistant", "content": txt}],
        }
    # Load all datasets specified
    frames = []
    for key, handle in datasets.items():
        try:
            df = pd.read_csv(handle["path"])
            frames.append((key, df))
        except Exception:
            continue
    if not frames:
        txt = "I fetched files but could not load them."
        return {
            "final": {"answer_text": txt},
            "messages": [{"role": "assistant", "content": txt}],
        }
    # Simple presentation
    if answer_type == "single":
        # Take first frame, first numeric var (not NAME/geo columns)
        key, df = frames[0]
        # pick the first variable (excluding NAME, for, in columns)
        var_cols = [
            c
            for c in df.columns
            if c
            not in (
                "NAME",
                "state",
                "place",
                "county",
                "tract",
                "block group",
                "year",
                "us",
            )
        ]
        value = df[var_cols[0]].iloc[0] if var_cols else "N/A"
        txt = f"Answer: {value} (from {key.replace('_', ' ')}, year {int(df['year'].iloc[0])})."
        return {
            "final": {"answer_text": txt},
            "messages": [{"role": "assistant", "content": txt}],
        }
    else:
        # Series/table: concatenate and provide a preview + saved table
        out_path = os.path.join(DATA_DIR, "result_table.csv")
        out_df = pd.concat(
            [df.assign(source_key=k) for k, df in frames], ignore_index=True
        )
        out_df.to_csv(out_path, index=False)
        prev = out_df.head(10).to_dict(orient="records")
        txt = "I assembled a table across the requested years. Showing a small preview."
        return {
            "final": {"answer_text": txt, "table_path": out_path, "preview": prev},
            "messages": [
                {
                    "role": "assistant",
                    "content": txt + f"\nPreview rows: {json.dumps(prev[:3])}",
                }
            ],
        }


def not_census_node(state: CensusState) -> Dict[str, Any]:
    txt = "This question doesn't look like a U.S. Census question. Could you rephrase or specify what Census measure you want?"
    return {
        "final": {"answer_text": txt},
        "messages": [{"role": "assistant", "content": txt}],
    }


# --------------------------
# Routers
# --------------------------
def route_from_intent(state: CensusState) -> str:
    intent = cast(Intent, state.get("intent") or {})
    if not intent.get("is_census", False):
        return "not_census"
    return "geo"


# --------------------------
# Build graph
# --------------------------
builder = StateGraph(CensusState)
builder.add_node("intent", intent_node)
builder.add_node("not_census", not_census_node)
builder.add_node("geo", geo_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("plan", plan_node)
builder.add_node("data", data_node)
builder.add_node("answer", answer_node)

builder.add_edge(START, "intent")
builder.add_conditional_edges(
    "intent", route_from_intent, {"not_census": "not_census", "geo": "geo"}
)
builder.add_edge("geo", "retrieve")
builder.add_edge("retrieve", "plan")
builder.add_edge("plan", "data")
builder.add_edge("data", "answer")
builder.add_edge("not_census", END)
builder.add_edge("answer", END)

graph = builder.compile()

# --------------------------
# Example run
# --------------------------
if __name__ == "__main__":
    # Example: "Hispanics income from 2012 to 2023 in NYC"
    init: CensusState = {
        "messages": [
            {"role": "user", "content": "Hispanics income from 2012 to 2023 in NYC"}
        ],
        "intent": None,
        "geo": None,
        "candidates": None,
        "plan": None,
        "artifacts": {"datasets": {}, "previews": {}},
        "logs": [],
        "final": None,
        "error": None,
    }
    out = graph.invoke(init)
    print("Final:", out.get("final"))
    print("Logs:", "\n".join(out.get("logs", [])))

# What you’ll likely customize next

# Intent with an LLM: Replace intent_node’s heuristic with a call to your chat model to extract is_census, answer_type, measures, time, geo_hint. Keep returning only the delta: {"intent": ...}.
# Geo resolver: Implement more robust mapping (states, counties, tracts). For tracts, you’ll need for=tract:* and in=state:..&in=county:..; consider adding a geocoder to map names → FIPS.
# Retrieval with a real vector DB:
# Build an index of Census variables (per dataset/year) using the Variables API. Use label + concept + universe as the embedding text; store var code, dataset, years_available in metadata.
# Implement VarIndex.similarity_search by calling your FAISS/Chroma/Pinecone index and returning docs with .metadata fields used above.
# Planning details:
# Enforce API limits (max number of variables per call).
# Split queries by year/geo if necessary.
# Data node:
# Add retries/backoff, API key param if you use one, and support additional geo levels.
# Save to Parquet for speed, and keep only handles + tiny previews in state.
# Answer node:
# Clean column names, pick correct measure column (e.g., *_001E), add friendly labels, basic charts, or richer summaries.
# If you share:

# Python version
# Vector DB (FAISS/Chroma/Pinecone/etc.)
# Where to store data (local path, S3, DB)
# Whether you want to use an LLM for intent/geo parsing (and which provider)
# …I’ll tailor this sketch (imports, index build, real vector DB code, and better geo handling) exactly to your stack.


# ------------- Chroma index -------------
import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR = "./chroma"
COLLECTION_NAME = "census_vars"

# Use a local sentence-transformer (swap for OpenAI if you prefer)
EMB = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def get_chroma() -> chromadb.Client:
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_collection():
    client = get_chroma()
    try:
        return client.get_collection(name=COLLECTION_NAME, embedding_function=EMB)
    except Exception:
        return client.create_collection(name=COLLECTION_NAME, embedding_function=EMB)


class ChromaVarIndex:
    def __init__(self, collection):
        self.col = collection

    def similarity_search(self, query: str, k: int = 10):
        res = self.col.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        docs = []
        # Chroma returns lists per query; we only sent 1 query
        for i in range(len(res.get("ids", [[]])[0])):
            md = res["metadatas"][0][i]
            dist = res["distances"][0][i] if "distances" in res else None
            score = 1 - dist if dist is not None else None  # cosine similarity approx
            docs.append({"metadata": md, "score": score})
        return docs


def load_var_index() -> ChromaVarIndex:
    col = get_collection()
    return ChromaVarIndex(col)


import requests, time, itertools

DATASETS = [
    # Add more if you want: "acs/acs1", decennial, etc.
    ("acs/acs5", range(2012, 2024)),  # 2012–2023
    # ("acs/acs1", range(2012, 2024)),
]


def fetch_variables(year: int, dataset: str) -> dict:
    # Returns a mapping var -> {label, concept, universe}
    url = f"https://api.census.gov/data/{year}/{dataset}/variables.json"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    js = r.json()
    variables = js.get("variables", {})
    out = {}
    for var, info in variables.items():
        # Skip non-estimate codes if you want only *_E; or keep all
        out[var] = {
            "label": info.get("label", ""),
            "concept": info.get("concept", ""),
            "universe": info.get("universe", ""),
        }
    return out


def build_aggregated_index():
    col = get_collection()
    # Aggregate by (dataset, var) across years, collecting years_available
    aggregated = {}  # (dataset, var) -> {label, concept, universe, years_available}
    for dataset, years in DATASETS:
        for y in years:
            try:
                vars_y = fetch_variables(y, dataset)
            except Exception as e:
                print(f"Skip {dataset} {y}: {e}")
                continue
            for var, meta in vars_y.items():
                key = (dataset, var)
                if key not in aggregated:
                    aggregated[key] = {
                        "label": meta["label"],
                        "concept": meta.get("concept", ""),
                        "universe": meta.get("universe", ""),
                        "years_available": set(),
                    }
                aggregated[key]["years_available"].add(y)
            time.sleep(0.1)  # be gentle

    # Prepare batches for Chroma
    ids, docs, mds = [], [], []
    for (dataset, var), meta in aggregated.items():
        years_list = sorted(list(meta["years_available"]))
        label = meta["label"] or var
        concept = meta.get("concept", "")
        universe = meta.get("universe", "")
        doc = f"{label}. Concept: {concept}. Universe: {universe}. Dataset: {dataset}"
        ids.append(f"{dataset}:{var}")
        docs.append(doc)
        mds.append(
            {
                "var": var,
                "label": label,
                "concept": concept,
                "universe": universe,
                "dataset": dataset,
                "years_available": years_list,
            }
        )

    # Upsert into Chroma in chunks
    B = 1000
    for i in range(0, len(ids), B):
        col.upsert(
            ids=ids[i : i + B], documents=docs[i : i + B], metadatas=mds[i : i + B]
        )
        print(f"Indexed {min(i + B, len(ids))}/{len(ids)}")
    print("Index build complete.")


if __name__ == "__main__":
    build_aggregated_index()


    def retrieve_node(state: CensusState) -> Dict[str, Any]:
    intent = cast(Intent, state.get("intent") or {})
    measures = intent.get("measures", [])
    answer_type = intent.get("answer_type", "single")
    time = intent.get("time", {})
    geo = cast(Geo, state.get("geo") or {})
    # Time hint string
    if "year" in time:
        time_hint = f"year {time['year']}"
    elif "start_year" in time and "end_year" in time:
        time_hint = f"years {time['start_year']} to {time['end_year']}"
    else:
        time_hint = ""
    # Build natural language query
    # Add common synonyms (e.g., Hispanic/Latino) to help matching
    meas_text = " ".join(measures)
    if "hispanic" in meas_text and "latino" not in meas_text:
        meas_text += " latino"
    q = f"{meas_text} {answer_type} ACS census variables {time_hint} dataset:acs/acs5"
    idx = load_var_index()
    docs = idx.similarity_search(q, k=10)

    variables: List[CandidateVar] = []
    for d in docs:
        md = d.get("metadata", {})
        if not md: 
            continue
        variables.append({
            "var": md.get("var"),
            "label": md.get("label", ""),
            "concept": md.get("concept", ""),
            "dataset": md.get("dataset", "acs/acs5"),
            "years_available": md.get("years_available", []),
            "score": d.get("score", 0.0),
        })

    # Fallbacks if index is empty
    if not variables and "population" in measures:
        variables = [{
            "var": "B01003_001E",
            "label": "Total population",
            "concept": "TOTAL POPULATION",
            "dataset": "acs/acs5",
            "years_available": list(range(2012, 2024)),
            "score": 0.99
        }]
    if not variables and "median_income" in measures and "hispanic" in measures:
        variables = [{
            "var": "B19013I_001E",
            "label": "Median household income in the past 12 months (Hispanic or Latino Householder)",
            "concept": "INCOME IN THE PAST 12 MONTHS",
            "dataset": "acs/acs5",
            "years_available": list(range(2012, 2024)),
            "score": 0.98
        }]

    # Pick years that intersect request and availability
    req_years = []
    if "year" in time: 
        req_years = [time["year"]]
    if "start_year" in time and "end_year" in time:
        req_years = list(range(time["start_year"], time["end_year"] + 1))

    if variables:
        avail = set(variables[0].get("years_available", []))
        years = [y for y in req_years if y in avail] or sorted(list(avail))[-1:]  # default to most recent
    else:
        years = []

    cand: Candidates = {"variables": variables, "years": years}
    return {"candidates": cand} | log(state, f"Retrieved {len(variables)} candidates")
