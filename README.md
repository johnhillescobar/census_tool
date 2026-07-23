# Census Tool

A local US Census question-answering application built with LangGraph, ChromaDB, and the Census API.

## Architecture

The graph is temporal-first:

`memory_load → temporal → geography → benchmark → comparison → agent → comparison_metrics → output → memory_write`

Deterministic nodes normalize and validate planning contracts. Geography is resolved only from versioned Chroma table,
hierarchy, and area candidates constrained by dataset and year. Missing or unhealthy evidence produces clarification; there is
no mapping fallback or implicit national default. The reasoning agent remains execution owner and uses strict typed Census API
tools under the validated plan.

- Current system reference: `app_description/ARCHITECTURE.md`
- Geography schemas and invariants: `docs/chroma_geography_architecture.md`
- Build, health, rollout, rollback, and debugging: `docs/chroma_geography_operator_runbook.md`
- Golden URL evidence: `migration_evidence/golden_urls/README.md`

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

- Temporal intent resolves before geography retrieval.
- Table search is mandatory for every data plan.
- Geography retrieval is filtered by selected table dataset and resolved year.
- Candidate IDs, exact Census tokens, parent order, and table compatibility are validated before execution.
- Profile geography is a retrieval hint, not authority.
- Empty, unavailable, stale, mismatched, or ambiguous evidence fails closed.
- Build-time Census `NAME,GEO_ID` enumeration remains supported for Chroma area population.

Supported contracts include nation, state, county, place, tract, block group, CBSA, metropolitan division, ZCTA, PUMA,
congressional and legislative districts, school districts, urban areas, and tribal hierarchies represented in the Census
catalog. Actual availability is dataset/year-specific.

## Acceptance

The golden corpus has 124 natural-language questions. The deterministic grounded replay validates 122 data rows through
candidate-ID selection and plan validation; two catalog URL rows are intentionally bypassed.

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
