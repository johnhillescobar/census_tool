# Census Tool

A local US Census question-answering application built with LangGraph, ChromaDB, and the Census API.

## Architecture

**Target (authoritative):** [`docs/agent-first-grounded-planning.md`](docs/agent-first-grounded-planning.md) — the agent reasons, retrieves semantically from Chroma, **composes Census API parameters**, **executes** tools (multi-call when needed), analyzes results, and may ask clarifying questions with grounded options.

**Current code (legacy):** temporal-first graph with pre-agent `geography_node` that can halt before the agent runs:

`memory_load → temporal → geography → benchmark → comparison → agent → comparison_metrics → output → memory_write`

Harness nodes validate typed contracts and fail closed on ungrounded IDs. Geography evidence comes from versioned Chroma table, hierarchy, and area candidates constrained by dataset and year. Missing or unhealthy evidence produces clarification; there is no mapping fallback or implicit national default.

- Target architecture: `docs/agent-first-grounded-planning.md`
- System reference: `app_description/ARCHITECTURE.md`
- Census API decision space (categories, `for`/`in`, multi-step): `app_description/CENSUS_DISCUSSION.md`
- Geography schemas and invariants: `docs/chroma_geography_architecture.md`
- Build, health, rollout, rollback, and debugging: `docs/chroma_geography_operator_runbook.md`
- Golden URL evidence: `migration_evidence/golden_urls/README.md`
- Jira ticket structure (CENSUS backlog): `docs/jira-ticket-structure.md`
- **Ticket execution workflow:** [Read → Reproduce → Plan → Implement → PR](docs/jira-ticket-structure.md#working-a-ticket-execution-workflow)

## Backlog and Jira workflow

When picking up a CENSUS issue, follow the pipeline in [Working a ticket](docs/jira-ticket-structure.md#working-a-ticket-execution-workflow):

`Read ticket → Reproduce / investigate → Plan (if fork) → Implement → PR`

- Hybrid ticket format (Context, Tasks, Acceptance criteria): `docs/jira-ticket-structure.md`
- Golden URL failure buckets and fix PR mapping: `migration_evidence/golden_urls/fix_pr_backlog_plan.md`
- One fix ticket → one PR; triage-only tickets (e.g. CENSUS-25) create Jira bugs, not code PRs

## Requirements and setup

- Python 3.12+
- `uv`
- An `OPENAI_API_KEY` for the configured LLM and Chroma embedding model
- A `CENSUS_API_KEY` for credentialed live acceptance

Install dependencies:

`uv sync`

Build the table and geography catalogs:

`uv run python index/build_index_table.py`

`uv run python index/build_geography_index.py`

Area indexes are built by dataset/year/level and reviewed parent partitions. For example:

`uv run python index/build_geography_areas_index.py --dataset acs/acs5 --year 2023 --level county --partition state:06`

Validate geography collection versions, manifests, age, and document counts:

`uv run python index/check_geography_index.py`

## Run

- Launcher: `uv run python launcher.py`
- CLI: `uv run python main.py`
- Streamlit: `uv run streamlit run streamlit_app.py`
- FastAPI: `uv run census-api`

Profiles and conversation history are local. SQLite checkpoints preserve graph state and pending clarification context across
turns.

## Grounded geography behavior

- Temporal intent resolves before catalog retrieval (default **`LATEST_AVAILABLE_YEAR`** from `config.py` when unstated — after `temporal_node`).
- **Target:** agent queries Chroma via tools for tables and geography; composes and executes Census API calls in multi-step loops.
- **Legacy (current code):** `geography_node` pre-selects table/geo before agent; may skip agent on clarification — migration in progress.
- Table and geography candidate IDs, exact Census tokens, parent order, and table compatibility are validated before execution (harness).
- Profile geography is a retrieval hint, not authority.
- Empty, unavailable, stale, mismatched, or ambiguous evidence fails closed.
- Build-time Census `NAME,GEO_ID` enumeration populates Chroma area documents (index build — not runtime planner authority).

Supported contracts include nation, state, county, place, tract, block group, CBSA, metropolitan division, ZCTA, PUMA,
congressional and legislative districts, school districts, urban areas, and tribal hierarchies represented in the Census
catalog. Actual availability is dataset/year-specific.

## Acceptance

The golden corpus has 124 natural-language questions. The **URL replay harness** validates 122 data rows through grounded candidate-ID selection and plan validation; two catalog URL rows are intentionally bypassed. Tier 3 NL UX follows agent-first intent (see `docs/agent-first-grounded-planning.md`).

Run the offline URL contract:

`uv run pytest app_test_scripts/test_census_url_fixtures.py app_test_scripts/test_golden_census_urls.py -q`

Run the grounded 124-question replay:

`uv run pytest app_test_scripts/test_phase6_golden_grounded_replay.py -q`

Run all non-integration tests:

`uv run pytest app_test_scripts -m "not integration" -q`

Run static quality gates:

`uv run ruff check .`

`uv run ruff format --check .`

Credentialed live acceptance and artifact export commands are in `migration_evidence/golden_urls/README.md`.

## Debugging and telemetry

Grounded retrieval writes JSON-line telemetry to `logs/telemetry.log`. Correlate analysis, retrieval, selection, validation, and
clarification events with `trace_id`.

VS Code includes:

- launch profiles for CLI, Streamlit, FastAPI, a chosen golden row, and pytest;
- tasks for unit tests, Tier 1 URLs, hierarchy/area builds, health, and telemetry;
- the breakpoint map at `.vscode/geography-breakpoints.md`.

Do not log API keys, complete environment dictionaries, or Census URLs after a key is appended.
