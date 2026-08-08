# Census Tool architecture

**Updated:** August 8, 2026  
**Status:** Agent-first grounded planning (target); legacy planner-first graph still in code — see migration section below.

**Authoritative target:** [`docs/agent-first-grounded-planning.md`](../docs/agent-first-grounded-planning.md)  
**Domain model (API composition):** [`CENSUS_DISCUSSION.md`](CENSUS_DISCUSSION.md)

## System shape (target)

The application is an **AI Census assistant** where the **agent** reasons about natural-language questions, queries Chroma for semantic evidence, **composes Census Bureau API parameters** (`get`/`for`/`in`, dataset path), **executes** Census tools (possibly many times in one turn), analyzes results, and narrates assumptions and follow-ups.

**Deterministic code is a harness only** — typed contracts, validators, strict Census API tool, retrieval traces, and comparison math **constrain** the agent at trust boundaries. They do **not** replace retrieval reasoning, table/geo selection, API composition, or multi-call strategy.

```
User question → temporal (year) → agent planning (Chroma tools) → validate grounded plan → agent execute → comparison_metrics → output
```

See [`docs/agent-first-grounded-planning.md`](../docs/agent-first-grounded-planning.md) for phased migration and acceptance criteria.

## LangGraph — target vs current

### Target graph (phased)

`memory_load → temporal → agent_plan → validate_plan → agent_execute → comparison_metrics → output → memory_write`

- **Agent planning turn:** semantic Chroma retrieval via agent tools; agent selects candidate IDs or asks a grounded clarifying question — **agent is not skipped**.
- **Validate harness:** `validate_grounded_plan` fail-closes on invented FIPS, table codes, or geo tokens not in evidence.
- **Agent execute turn:** agent composes and invokes `StrictCensusApiTool` / enumeration tools in a multi-step loop as reasoning requires.
- **Comparison metrics:** deterministic formulas on typed rows (not LLM).

### Current graph (legacy — migration debt)

`app.py:create_census_graph()` today:

`memory_load → temporal → geography → benchmark → comparison → agent → comparison_metrics → output → memory_write`

**Documentation drift:** The code path above is **planner-first**. `geography_node` runs **before** the agent, may halt the graph with `requires_clarification=True`, and routes to `output` with the agent skipped (`src/workflows/agent.py`). When the agent runs, it often receives an **immutable** `GroundedCensusPlan` rather than owning API parameter construction end-to-end.

Do **not** extend this path with new allowlists, score-rank auto-select policy, or planner-only fixes. Interim tickets (e.g. CENSUS-21 table-slot resume) patch the legacy graph; they are **not** the end state.

- `memory_load` routes checkpointed geography choices to `geography_resume` (legacy resume — target: agent turn with grounded options).
- Temporal, geography, benchmark, comparison nodes may short-circuit to `output` with clarification; **target:** agent-driven dialogue instead of raw `table_0` dumps with `agent: skipped`.
- `comparison_metrics` computes deterministic metrics from agent-produced typed rows.
- `memory_write` persists the completed turn.

All workflow updates use `CensusGraphPatch`. `WorkflowPlan` is the planning aggregate; `state.geo` is its typed resolved projection.

## Runtime planning (target)

The agent — via tools — owns the decision space in [`CENSUS_DISCUSSION.md`](CENSUS_DISCUSSION.md):

| Step | Owner (target) | Harness |
| --- | --- | --- |
| Resolve year | `temporal_node` (default latest e.g. 2024 when unstated) | `TemporalIntent` contract |
| Semantic table/geo retrieval | Agent tools (`TableSearchTool`, `GeographyDiscoveryTool`, …) | Year/dataset filters; `RetrievalEvidence` |
| Category, table, variables, `for`/`in` | Agent reasoning + API composition | `validate_grounded_plan`; strict Census API tool |
| Multi-call loops (enumerate → disambiguate → fetch) | Agent tool loop | Fail-closed on ungrounded codes |
| Clarification | Agent dialogue with grounded labels + recommended default | Checkpoint stores evidence snapshot |
| Answer + follow-ups | Agent narration | Presentation routing from typed state |

Chroma collections (`census_tables`, `census_dataset_geographies`, `census_geography_areas`) supply **evidence**, not authority. Only **selected candidate IDs** attached to evidence become execution authority after validation.

Index build (deterministic IDs, manifests) is separate from runtime retrieval (agent semantic query). Schemas and invariants: `docs/chroma_geography_architecture.md`; operations: `docs/chroma_geography_operator_runbook.md`.

## Legacy planner path (migration debt)

`src/workflows/geography.py` (`geography_node`) currently performs this sequence **before** the agent:

1. Analyze the question into search phrases (`DeterministicCensusRetrievalAnalyzer` — regex, not agent retrieval).
2. Retrieve table candidates for the temporally resolved year.
3. **Score-rank auto-select** one table (`select_grounded_plan`) or halt with table clarification.
4. Require explicit geography text or a profile hint; absence requires clarification.
5. Retrieve hierarchy and area candidates constrained by selected dataset and year.
6. Select only supplied candidate IDs.
7. Validate IDs, table compatibility, exact Census tokens, and parent ordering.
8. Store grounded plan, evidence, and retrieval trace; project `GeographyIntent(source="chroma")`.

**Lose as authority (do not document as primary path):** regex analyzer as graph entry, score-rank auto-select, pre-agent graph halt, `requires_clarification` agent skip, planner code allowlists, immutable upstream URL assembly.

**Keep as harness (refactor in place):** evidence attachment, `RetrievalTrace`, `validate_grounded_plan`, fail-closed on stale/empty/malformed evidence, strict Census API tool.

There is no implicit US default in the grounded path. Missing, unavailable, stale, empty, ambiguous, or malformed evidence fails closed.

Typed contracts and manifests: `src/domain/geography_catalog.py`.

## Contracts (harness language)

| Contract | Responsibility |
| --- | --- |
| `TemporalIntent` | point, range, rolling, or latest time scope |
| `GeographyIntent` | validated `geo_for`, ordered context projected as `geo_in`, display name, source |
| `RetrievalEvidence` | collection status, query, versions, candidate IDs, typed candidates |
| `GroundedSelection` | selected candidate IDs and attached evidence IDs |
| `GroundedCensusPlan` | validated table and geography execution authority (agent-proposed, harness-validated) |
| `BenchmarkIntent` / `ComparisonPlan` | comparison target, years, metric, operation, normalization |
| `AgentPlanContext` / `ExecutionSpec` | execution obligations passed to agent after validation |
| `AgentPlanOutput` | validated agent data and presentation directives |
| `StrictCensusApiResponse` | typed Census API tool result |
| `RetrievalTrace` | stage-by-stage retrieval and validation receipt |

Pydantic contracts reject extra fields at trust boundaries where specified. The strict Census API tool rejects requests that do not agree with grounded evidence.

## Agent and tools

`CensusQueryAgent` uses the modern runtime backend. **Target:** agent receives resolved temporal year and retrieval tools on turn 1; composes API parameters per `CENSUS_DISCUSSION.md`; executes via tools in multi-call loops.

Active tools cover grounded geography discovery and validation, table search, strict and compatibility Census calls, pattern construction, area resolution, hierarchy inspection, variable validation, and output generation (`src/agents/census_query_agent.py`).

Build-time Census enumeration remains in `index/`; it populates Chroma and is not runtime decision authority.

## State, persistence, and presentation

`CensusState` uses typed reducer channels for messages, plan, artifacts, final response, profile, cache index, and logs. LangGraph checkpoints use SQLite with an in-memory fallback. Pending clarification stores trace and index version; resume rejects stale or mismatched evidence.

Presentation routing derives from typed state, not agent prose. Output nodes render only successful Census payloads and validated comparison rows.

## Observability

`src/clients/telemetry.py` writes JSON-line events to `logs/telemetry.log`. Grounded retrieval events include trace ID, stage, status, reason, collection, filters, candidates, and selections.

Use `.vscode/geography-breakpoints.md` (legacy path map), the `Geography: Golden row 3` launch profile, and `scripts/debug_geography_query.py` for node-by-node inspection of the **current** graph.

## Acceptance

The committed corpus has 124 questions: 122 data URLs replay through candidate selection and validation (URL replay harness), while two catalog URLs are intentionally bypassed. Tier 3 NL UX is agent-first; golden replay validates grounded ID contracts, not planner auto-select policy.

- Offline URL contract: `uv run pytest app_test_scripts/test_census_url_fixtures.py app_test_scripts/test_golden_census_urls.py -q`
- Grounded replay: `uv run pytest app_test_scripts/test_phase6_golden_grounded_replay.py -q`
- Full non-integration suite: `uv run pytest app_test_scripts -m "not integration" -q`
- Static quality: `uv run ruff check . && uv run ruff format --check .`

Live Tier 2 and Tier 3 commands, artifact semantics, and evidence naming: `migration_evidence/golden_urls/README.md`.
