# Chroma geography debug queries

Companion to [chroma_geography_operator_runbook.md](./chroma_geography_operator_runbook.md). Use these commands when grounded geography fails or table retrieval returns `TABLE_SCHEMA_MISMATCH`.

If you see `TABLE_SCHEMA_MISMATCH` / legacy bare table ids (`B01003` without `table:` prefix), rebuild with the orchestrator (do not upsert onto the mixed collection):

`uv run python index/rebuild_catalog.py --staging chroma-staging --serving chroma --year-start 2014 --components tables --promote`

## Preconditions

- Run from the repository root.
- `.env` loaded (or set keys manually):
  - `OPENAI_API_KEY` — required for semantic `query()` on `census_tables`
  - Chroma collections expect `CHROMA_OPENAI_API_KEY`; the debug script bridges from `OPENAI_API_KEY` if unset
- `CENSUS_API_KEY` — only needed for full graph runs that hit the Census API later

## Primary tool: `scripts/debug_geography_query.py`

### Table index only (no LangGraph)

Fastest way to diagnose `TABLE_SCHEMA_MISMATCH` before geography runs:

```powershell
python scripts/debug_geography_query.py --inspect-only --table-query "total population"
```

Golden row 3 (California counties population), with year aligned to the question:

```powershell
python scripts/debug_geography_query.py --inspect-only --golden-row 3 --planning-year 2023
```

### Inspect tables, then run the graph

```powershell
python scripts/debug_geography_query.py --inspect-tables --golden-row 3 --show-candidates
```

Stop after a specific node:

```powershell
python scripts/debug_geography_query.py --golden-row 3 --stop-after geography --show-candidates
```

### Flags

| Flag | Purpose |
|------|---------|
| `--inspect-only` | Table Chroma diagnostics only; exit without graph |
| `--inspect-tables` | Run diagnostics, then continue to LangGraph |
| `--table-query "..."` | Override table search text (default: analyzer output from question) |
| `--planning-year 2023` | Year filter for grounded table retrieval (default: `LATEST_AVAILABLE_YEAR` from `config.py`) |
| `--peek-limit 5` | Rows sampled via `collection.peek()` |
| `--golden-row N` | Question from golden URL fixtures |
| `--show-candidates` | Include retrieval candidates in graph JSON output |

## What the inspection prints

Four sections, in order:

1. **`[collection metadata]`** — `schema_version`, `index_version`, `built_at`, document count
   - If `schema_version_ok=False` or `index_version_ok=False` → collection-level mismatch; rebuild or promote a fresh index.

2. **`[chroma query: parse + embed]`** — `query_table_collection` result
   - **`reason`** is the smoking gun (not shown on `RetrievalEvidence` in graph output).
   - Example failure: `reason='Chroma id and metadata candidate_id do not match'`

3. **`[grounded table retrieval: app path with year filter]`** — same retriever as legacy `geography_node` (`retrieve_table_candidates`); **target:** agent tool invokes this path
   - If this is `schema_mismatch`, geography never runs.

4. **`[peek sample]`** — raw stored rows without embedding
   - Checks: `id_matches_candidate_id`, `year`, `years_available`, `parse_status`

## Interpreting common failures

### Collection metadata OK, query `schema_mismatch`

Collection headers can be valid while **document metadata** is from an older index build.

**Symptoms (verified on golden row 3):**

```
[chroma query: parse + embed]
status=schema_mismatch
reason='Chroma id and metadata candidate_id do not match'

[peek sample]
chroma_id='B17015'
id_matches_candidate_id=False
year=None
parse_error=ValueError: Chroma id and metadata candidate_id do not match ('B17015' vs None)
```

**Cause:** Old `census_tables` rows use ids like `B17015` and omit catalog contract fields (`candidate_id`, `year`, `provenance`, `schema_version`). The parser in `src/clients/chroma_utils.py` requires id == `metadata.candidate_id`.

**Fix:** Rebuild tables per runbook Step 1:

```powershell
uv run python index/build_index_table.py
```

Expected new id shape: `table:acs/acs5:B01003` (see `index/build_index_table.py`).

### Graph shows `GEOGRAPHY_NOT_FOUND` but trace says `TABLE_SCHEMA_MISMATCH`

`normalize_geography_reason()` maps many table failures to a geography-not-found user message. Trust:

- `retrieval_trace` → `TABLE_RETRIEVAL` → `reason_code=TABLE_SCHEMA_MISMATCH`
- `pending_geography_clarification.requested_slot='table'`

This is not a geography search failure — table retrieval failed first.

### `planning_year` mismatch

Inspection defaults to `LATEST_AVAILABLE_YEAR` (2024). Golden row 3 asks for **2023**. Use:

```powershell
python scripts/debug_geography_query.py --inspect-only --golden-row 3 --planning-year 2023
```

Year mismatch alone causes `empty` after a successful parse; it does **not** cause `schema_mismatch`.

## Full graph debug (after table index is healthy)

```powershell
python scripts/debug_geography_query.py --golden-row 3 --show-candidates
```

VS Code launch profiles (`.vscode/launch.json`):

- **Geography: Golden row 3**
- **Geography: Choose golden row**

Both load `.env` and set `PYTHONPATH`.

## Geography index health (separate from tables)

Tables are **not** covered by `check_geography_index.py`:

```powershell
uv run python index/check_geography_index.py --persist-dir chroma
```

Use the table inspection commands above for `census_tables`.

## Decision tree

```
debug_geography_query.py --inspect-only ...
│
├─ schema_version_ok=False  → rebuild/promote collection metadata
│
├─ chroma query reason mentions candidate_id  → rebuild census_tables (old document schema)
│
├─ chroma query status=empty (reason None)    → re-embed / wrong query text / empty index
│
├─ grounded status=empty after hit            → year filter (--planning-year)
│
└─ table hit, geography fails                 → geography index / areas (see operator runbook)
```

## Related files

| File | Role |
|------|------|
| `scripts/debug_geography_query.py` | Inspection + graph stream |
| `src/clients/chroma_utils.py` | `_collection_health`, `_candidate_from_metadata` |
| `src/workflows/geography.py` | Table retrieval before geography |
| `docs/chroma_geography_operator_runbook.md` | Build, promote, rollback |
| `.vscode/geography-breakpoints.md` | Debugger breakpoint map |
