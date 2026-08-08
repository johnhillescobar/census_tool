# Chroma geography debug queries

Companion to [chroma_geography_operator_runbook.md](./chroma_geography_operator_runbook.md). Use these commands when grounded geography fails or table retrieval returns `TABLE_SCHEMA_MISMATCH`.

If you see `TABLE_SCHEMA_MISMATCH` / legacy bare table ids (`B01003` without `table:` prefix), rebuild with the orchestrator (do not upsert onto the mixed collection):

`uv run python index/rebuild_catalog.py --staging chroma-staging --serving chroma --year-start 2014 --components tables --promote`

## Preconditions

- Run from the repository root.
- `.env` loaded (or set keys manually):
  - `OPENAI_API_KEY` — required when the graph hits Chroma semantic retrieval
  - `CENSUS_API_KEY` — only needed for graph runs that reach Census API execution
- Default planning year when the question omits a year: `LATEST_AVAILABLE_YEAR` in [`config.py`](../../config.py) (currently **2024** after the 2024 Chroma catalog update)

## Primary tool: `scripts/debug_geography_query.py`

The script streams LangGraph node updates for one question and prints JSON patches. **Supported flags only:**

| Flag | Purpose |
|------|---------|
| `--question "..."` | Natural-language question (mutually exclusive with `--golden-row`) |
| `--golden-row N` | Question from golden URL fixtures |
| `--stop-after NODE` | Stop after the named node emits an update (e.g. `geography`) |
| `--thread-id ID` | Checkpoint thread id (default: `vscode-geography-debug`) |
| `--show-candidates` | Include retrieval `candidates` in printed JSON (omitted by default) |

### Golden row 3 (California counties population)

```powershell
uv run python scripts/debug_geography_query.py --golden-row 3 --show-candidates
```

Stop after the legacy geography planner node:

```powershell
uv run python scripts/debug_geography_query.py --golden-row 3 --stop-after geography --show-candidates
```

### Custom question

```powershell
uv run python scripts/debug_geography_query.py --question "Show total population for all California counties in 2023." --show-candidates
```

### Output format

The script prints:

1. `question='...'` and `checkpoint=...` (temp SQLite path)
2. For each node update: `[node_name]` followed by indented JSON from `graph.stream(..., stream_mode="updates")`

Use `--show-candidates` to inspect `RetrievalEvidence.candidates` inside geography/table patches. Without it, large candidate lists are stripped for readability.

## Table schema mismatches (no separate inspect mode)

`debug_geography_query.py` does **not** implement `--inspect-only`, `--inspect-tables`, `--table-query`, `--planning-year`, or `--peek-limit`. For table index health:

1. **Rebuild tables** — runbook Step 1 / orchestrator command above
2. **Check geography collections** (not `census_tables`):

```powershell
uv run python index/check_geography_index.py --persist-dir chroma
```

3. **Re-run graph debug** with `--show-candidates` and inspect `[geography]` patch for `retrieval_trace`, `reason_code`, and `pending_geography_clarification`

### Interpreting common failures in graph output

**`TABLE_SCHEMA_MISMATCH` / old Chroma ids**

- Symptom in trace: `reason_code=TABLE_SCHEMA_MISMATCH` or parse errors mentioning `candidate_id`
- Cause: Old `census_tables` rows use bare ids like `B17015` without catalog contract metadata
- Fix: Rebuild tables per runbook; expected id shape: `table:acs/acs5:B01003`

**`GEOGRAPHY_NOT_FOUND` when trace says table failed first**

- `normalize_geography_reason()` may map table failures to geography-not-found copy
- Trust `retrieval_trace` → `TABLE_RETRIEVAL` and `pending_geography_clarification.requested_slot='table'`

**Year mismatch (question says 2023, default catalog year is `LATEST_AVAILABLE_YEAR`)**

- Golden row 3 asks for **2023**; unstated-year defaults use `config.LATEST_AVAILABLE_YEAR` (**2024**)
- Symptom: empty table hits or wrong-year candidates — not `schema_mismatch`
- Fix: include the year in the question (row 3 already does) or verify temporal resolution in the `[temporal]` patch

## VS Code integration

Launch profiles (`.vscode/launch.json`):

- **Geography: Golden row 3**
- **Geography: Choose golden row**

Both load `.env` and set `PYTHONPATH`. Breakpoint map: [`.vscode/geography-breakpoints.md`](../.vscode/geography-breakpoints.md) (legacy planner path).

## Related files

| File | Role |
|------|------|
| `scripts/debug_geography_query.py` | Graph stream debugger |
| `src/clients/chroma_utils.py` | Collection health and candidate parsing |
| `src/workflows/geography.py` | Legacy pre-agent table/geo retrieval |
| `docs/chroma_geography_operator_runbook.md` | Build, promote, rollback |
| `config.py` | `LATEST_AVAILABLE_YEAR`, catalog year ranges |
