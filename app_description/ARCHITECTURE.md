# Census Tool architecture

**Updated:** July 21, 2026
**Status:** temporal-first planning with Chroma-grounded geography and agent-owned execution

## System shape

The application combines deterministic planning contracts with a reasoning agent. Planning resolves time first, then builds a
table-and-geography plan exclusively from retrieved Chroma candidates. The agent remains execution owner: it performs strict
Census API calls and chooses answer, chart, and table directives within the immutable plan.

Deterministic planning is reliability scaffolding; it does not replace the reasoning node.

## LangGraph

`app.py:create_census_graph()` builds ten nodes, including checkpoint resume:

`memory_load → temporal → geography → benchmark → comparison → agent → comparison_metrics → output → memory_write`

- `memory_load` routes checkpointed geography choices to `geography_resume`.
- Temporal, geography, benchmark, comparison, and agent nodes route typed clarification directly to `output`.
- Benchmark may bypass comparison when it is not applicable.
- `comparison_metrics` computes deterministic metrics from agent-produced typed rows.
- `memory_write` persists the completed turn.

All workflow updates use `CensusGraphPatch`. `WorkflowPlan` is the planning aggregate; `state.geo` is its typed resolved
projection.

## Grounded geography

`src/workflows/geography.py` performs this sequence:

1. Analyze the question into search phrases without producing canonical Census codes.
2. Retrieve table candidates for the temporally resolved year.
3. Select one retrieved table candidate.
4. Require explicit geography text or a profile hint; absence requires clarification.
5. Retrieve hierarchy and area candidates constrained by the selected dataset and year.
6. Select only supplied candidate IDs.
7. Validate IDs, table compatibility, exact Census tokens, and parent ordering.
8. Store the grounded plan, evidence, and retrieval trace; project a `GeographyIntent(source="chroma")`.

There is no feature flag, legacy mapping fallback, LLM geography resolver, pickle-backed runtime authority, or implicit US
default in this path. Missing, unavailable, stale, empty, ambiguous, or malformed evidence fails closed.

The three active collections are `census_tables`, `census_dataset_geographies`, and `census_geography_areas`. Their typed
contracts and manifests are defined in `src/domain/geography_catalog.py`. Detailed schemas and invariants are in
`docs/chroma_geography_architecture.md`; operations are in `docs/chroma_geography_operator_runbook.md`.

## Contracts

| Contract | Responsibility |
| --- | --- |
| `TemporalIntent` | point, range, rolling, or latest time scope |
| `GeographyIntent` | validated `geo_for`, ordered context projected as `geo_in`, display name, source |
| `RetrievalEvidence` | collection status, query, versions, candidate IDs, typed candidates |
| `GroundedSelection` | selected candidate IDs and attached evidence IDs |
| `GroundedCensusPlan` | validated table and geography execution authority |
| `BenchmarkIntent` / `ComparisonPlan` | comparison target, years, metric, operation, normalization |
| `AgentPlanContext` / `ExecutionSpec` | immutable execution obligations |
| `AgentPlanOutput` | validated agent data and presentation directives |
| `StrictCensusApiResponse` | typed Census API tool result |
| `RetrievalTrace` | stage-by-stage retrieval and validation receipt |

Pydantic contracts reject extra fields at trust boundaries where specified. The strict Census API tool rejects requests that
do not agree with grounded evidence.

## Agent and tools

`CensusQueryAgent` uses the modern runtime backend and receives `AgentPlanContext`. Active tools cover grounded geography
discovery and validation, table search, strict and compatibility Census calls, pattern construction, area resolution,
hierarchy inspection, variable validation, and output generation.

The old `TableValidationTool` is not registered because runtime table/geography compatibility is enforced before execution by
grounded plan validation. Build-time Census enumeration remains in `index/`; it populates Chroma and is not called as runtime
authority.

## State, persistence, and presentation

`CensusState` uses typed reducer channels for messages, plan, artifacts, final response, profile, cache index, and logs.
LangGraph checkpoints use SQLite with an in-memory fallback. A pending geography clarification stores trace and index version,
so resume rejects stale or mismatched evidence.

Presentation routing derives from typed state, not agent prose. Output nodes render only successful Census payloads and
validated comparison rows.

## Observability

`src/clients/telemetry.py` writes JSON-line events to `logs/telemetry.log`. Grounded retrieval events include trace ID, stage,
status, reason, collection, filters, candidates, and selections. Release metrics detect blocked geography, invented IDs,
implicit national scope, and silent Chroma misses.

Use `.vscode/geography-breakpoints.md`, the `Geography: Golden row 3` launch profile, and
`scripts/debug_geography_query.py` for node-by-node inspection.

## Acceptance

The committed corpus has 124 questions: 122 data URLs replay through candidate selection and validation, while two catalog
URLs are intentionally bypassed.

- Offline URL contract: `uv run pytest app_test_scripts/test_census_url_fixtures.py app_test_scripts/test_golden_census_urls.py -q`
- Grounded replay: `uv run pytest app_test_scripts/test_phase6_golden_grounded_replay.py -q`
- Full non-integration suite: `uv run pytest app_test_scripts -m "not integration" -q`
- Static quality: `uv run ruff check . && uv run ruff format --check .`

Live Tier 2 and Tier 3 commands, artifact semantics, and evidence naming are documented in
`migration_evidence/golden_urls/README.md`.
