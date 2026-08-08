# Chroma geography debug queries

Companion to [chroma_geography_operator_runbook.md](./chroma_geography_operator_runbook.md). Use these commands when grounded geography fails or table retrieval returns `TABLE_SCHEMA_MISMATCH`.

If you see `TABLE_SCHEMA_MISMATCH` / legacy bare table ids (`B01003` without `table:` prefix), rebuild with the orchestrator (do not upsert onto the mixed collection):

`uv run python index/rebuild_catalog.py --staging chroma-staging --serving chroma --year-start 2014 --components tables --promote`

## Preconditions

- Run from the repository root.
- `.env` loaded (or set keys manually):
  - `OPENAI_API_KEY` — required when the graph hits Chroma semantic retrieval
  - Chroma collections expect `CHROMA_OPENAI_API_KEY`; the debug script bridges from `OPENAI_API_KEY` if unset
  - `CENSUS_API_KEY` — only needed for graph runs that reach Census API execution
- Default planning year when the question omits a year: `LATEST_AVAILABLE_YEAR` in [`config.py`](../config.py) (currently **2024** after the 2024 Chroma catalog update)

## Primary tool: `scripts/debug_geography_query.py`

Supports **table index inspection** (Chroma-only) and **LangGraph stream debug** (legacy planner path today).

### Table index only (no LangGraph)

Fastest way to diagnose `TABLE_SCHEMA_MISMATCH` before geography runs:

```powershell
uv run python scripts/debug_geography_query.py --inspect-only --table-query "total population"
```

Golden row 3 (California counties population), with year aligned to the question:

```powershell
uv run python scripts/debug_geography_query.py --inspect-only --golden-row 3 --planning-year 2023
```

### Inspect tables, then run the graph

```powershell
uv run python scripts/debug_geography_query.py --inspect-tables --golden-row 3 --show-candidates
```

### Graph stream debug

Golden row 3:

```powershell
uv run python scripts/debug_geography_query.py --golden-row 3 --show-candidates
```

Stop after the legacy geography planner node:

```powershell
uv run python scripts/debug_geography_query.py --golden-row 3 --stop-after geography --show-candidates
```

Custom question:

```powershell
uv run python scripts/debug_geography_query.py --question "Show total population for all California counties in 2023." --show-candidates
```

### Flags

| Flag | Purpose |
|------|---------|
| `--inspect-only` | Table Chroma diagnostics only; exit without graph |
| `--inspect-tables` | Run diagnostics, then continue to LangGraph |
| `--table-query "..."` | Override table search text (default: analyzer output from question) |
| `--planning-year 2023` | Year filter for table retrieval inspection (default: `LATEST_AVAILABLE_YEAR`) |
| `--peek-limit 5` | Rows sampled via `collection.peek()` |
| `--question "..."` | Natural-language question (mutually exclusive with `--golden-row`) |
| `--golden-row N` | Question from golden URL fixtures |
| `--stop-after NODE` | Stop after the named node emits an update (e.g. `geography`) |
| `--thread-id ID` | Checkpoint thread id (default: `vscode-geography-debug`) |
| `--show-candidates` | Include retrieval `candidates` in graph JSON output |

### Graph output format

1. `question='...'` and `checkpoint=...` (temp SQLite path)
2. For each node update: `[node_name]` followed by indented JSON from `graph.stream(..., stream_mode="updates")`

Use `--show-candidates` to inspect `RetrievalEvidence.candidates` inside geography/table patches.

## What the inspection prints

Four sections, in order:

1. **`[collection metadata]`** — `schema_version`, `index_version`, `built_at`, document count
2. **`[chroma query: parse + embed]`** — `query_table_collection` result; **`reason`** is the smoking gun
3. **`[grounded table retrieval: app path with year filter]`** — same path as legacy `geography_node` (`retrieve_table_candidates`)
4. **`[peek sample]`** — raw stored rows without embedding

## Interpreting common failures

### Collection metadata OK, query `schema_mismatch`

Old `census_tables` rows use ids like `B17015` and omit catalog contract fields. Fix: rebuild tables per runbook; expected id shape: `table:acs/acs5:B01003`.

### Graph shows `GEOGRAPHY_NOT_FOUND` but trace says table failure

Trust `retrieval_trace` → `TABLE_RETRIEVAL` and `pending_geography_clarification.requested_slot='table'`.

### `planning_year` mismatch

Golden row 3 asks for **2023**; unstated-year defaults use `LATEST_AVAILABLE_YEAR` (**2024**). Use `--planning-year 2023` for inspection or verify temporal resolution in the `[temporal]` patch.

## Geography index health (separate from tables)

```powershell
uv run python index/check_geography_index.py --persist-dir chroma
```

## Decision tree

```
debug_geography_query.py --inspect-only ...
│
├─ schema_version_ok=False  → rebuild/promote collection metadata
├─ chroma query reason mentions candidate_id  → rebuild census_tables (old document schema)
├─ chroma query status=empty (reason None)    → re-embed / wrong query text / empty index
├─ grounded status=empty after hit            → year filter (--planning-year)
└─ table hit, geography fails                 → geography index / areas (see operator runbook)
```

## VS Code integration

Launch profiles (`.vscode/launch.json`): **Geography: Golden row 3**, **Geography: Choose golden row**. Breakpoint map: [`.vscode/geography-breakpoints.md`](../.vscode/geography-breakpoints.md) (legacy planner path).

## Related files

| File | Role |
|------|------|
| `scripts/debug_geography_query.py` | Table inspection + graph stream debugger |
| `src/clients/chroma_utils.py` | Collection health and candidate parsing |
| `src/workflows/geography.py` | Legacy pre-agent table/geo retrieval |
| `docs/chroma_geography_operator_runbook.md` | Build, promote, rollback |
| `config.py` | `LATEST_AVAILABLE_YEAR`, catalog year ranges |
