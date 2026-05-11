# Track 2 - Strict Pydantic State Ownership Map

Refresh: 2026-05-04. This ownership map remains active, but status details
that mentioned the 2026-04-26 test collection blocker, Streamlit dead-schema
rendering, or the agent footnote `model_dump()` bridge are superseded by
`migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`.

## Scope
- Goal: Define ownership for Track 2 strict state contracts, deterministic computation path, and required serialization boundaries.
- Rule: Track 2 now includes strict Pydantic state migration for most of `CensusState`, plus the consumers and persistence layers required to keep those state contracts intact end-to-end.
- Canonical principle: deterministic contracts and workflow/service steps are reliability scaffolding that empower AI reasoning nodes/components and must not replace AI reasoning nodes/components.
- Architecture invariant: Pydantic typed contracts prevent malformed objects at the earliest boundary (from the start), deterministic gates produce typed artifacts, and reasoning consumes those artifacts to execute tool loops and synthesize outputs.
- Architecture invariant: reasoning is not the primary contract-validation owner; deterministic typed boundaries own malformed-object prevention and fail-closed validation.
- Temporal/benchmark/comparison nodes clarify and gate ambiguous input early.
- The reasoning node remains the execution owner, performs repeated strict typed Census tool calls as needed, and drives answer/table/chart directives.
- Out of scope: provenance enforcement (Track 3), dependency/runtime modernization (Track 4).
- Layer order: `domain -> clients -> services -> agents -> workflows -> api`

## Status Legend

- `T2-P1`: implement first (contract and deterministic foundations)
- `T2-P2`: implement second (workflow integration and canonical coverage)
- `T2-P3`: implement last (refinements, docs hardening)

## Track 2 Gate Split

- Track 2A - Deterministic Planning Complete: closed 2026-05-04. Evidence:
  `migration_evidence/track2_progress_20260504/track2a_closeout.md`.
- Track 2B - Typed Workflow State: state/workflow/agent ownership for strict
  graph channels, reducers/adapters, and authoritative `census_data` flow.
- Track 2C - Output, UI, And Persistence Hardening: workflow/api/client
  ownership for render DTOs, display adapters, chart/table compatibility, and
  versioned memory persistence.
- Track 2D - Tooling And Governance: repo tooling and migration evidence
  ownership for `mypy`, dependency-freeze reconciliation, and final gate docs.

## Track 2 Ownership Map

| Artifact / Module | Target owner layer | Why this owner | Depends on | Used by | Priority | Notes |
|---|---|---|---|---|---|---|
| `TemporalIntent` model | `domain` | Canonical typed temporal normalization contract | Pydantic only | services, workflows | T2-P1 | Must enforce explicit mode/year/policy enums |
| `BenchmarkIntent` model | `domain` | Canonical benchmark semantics contract | Pydantic only | services, workflows | T2-P1 | Must encode comparison op + normalization mode; `historical_baseline` is currently fail-closed (temporary) until explicit baseline fields/validators are added |
| `ComparisonPlan` model | `domain` | Canonical plan object for deterministic query matrix | Pydantic only | services, workflows, agents | T2-P1 | Must carry join keys + derived metric plan |
| Core workflow state models (`messages`, `intent`, `geo`, `plan`, `artifacts`, `final`) | `state` | Keep graph state typed end-to-end and stop generic dict handoffs | domain contracts + LangGraph reducer constraints | workflows, agents, output, api | T2-P1 | Partial progress landed: `plan`, `artifacts`, and `final` now have typed envelopes, but the remaining state channels and artifact interiors are still loose and must be migrated before Track 2 exit |
| Persistence state models (`profile`, `history`, `cache_index`) | `state` + `services` | Keep memory-backed state typed while supporting schema migration | state contracts + migration adapters + file I/O | workflows, clients | T2-P1 | New JSON schema is allowed; migration path must be explicit and versioned |
| Serialization adapters | `clients` + `workflows` boundary | Restrict `model_dump()` to true serialization boundaries only | typed state models + JSON file format + external lib requirements | memory write, UI/tool bridges | T2-P1 | Allowed boundaries: disk persistence and explicit external payload conversion |
| Temporal normalization logic | `services` | Deterministic transformation from user request to intent | domain contracts + dataset availability | workflows | T2-P1 | No model-driven math decisions |
| Benchmark planning logic | `services` | Deterministic benchmark set resolution | domain contracts + geography/data rules | workflows | T2-P1 | Must fail to clarification on unresolved benchmark |
| Query expansion logic (year x geo matrix) | `services` | Deterministic expansion from plan to API specs | domain contracts + client request DTOs | workflows | T2-P1 | Stable ordering required for repeatability. **Status: implemented** (`src/services/comparison_plan_policy.py`) |
| Derived comparison metric compute | `services` | Deterministic numeric computation boundary | API result frames + plan contract | workflows, output synthesis | T2-P1 | Never delegated to LLM text reasoning. **Status: implemented in service code, partial in workflow storage** (`src/services/comparison_metric_compute.py`, `src/workflows/comparison_metrics.py`) |
| Tool input contract enforcement (planning-critical tools) | `services` + `tools` boundary | Ensure tool entry points reject raw/malformed payloads and accept only typed validated input | domain contract models + tool input schemas | agents, workflows | T2-P1 | Partial progress landed: geography/variable planning tools now expose typed schemas and typed responses, but compatibility shims and legacy loose wrappers still remain before Track 2 exit |
| Planning orchestration nodes | `workflows` | Sequence and typed handoff enforcement | services + state typing | app/workflow entry | T2-P2 | Partial progress landed: core planning nodes now hand off typed plan payloads, but the broader graph still contains loose state/artifact channels and dict-based adapters |
| Reasoning execution loop (tool use + synthesis) | `agents` | Owns multi-step execution against typed artifacts and tool outputs | typed planning artifacts + typed tools | workflows, output | T2-P2 | Reasoning node calls strict Census tool(s) as needed and produces answer/table/chart directives |
| Workflow state typing updates | `workflows` / `state` | Preserve contract consistency across nodes | domain contracts | workflows | T2-P2 | Remove raw dict handoff across the full graph; current `CensusState` generic dict channels are not sufficient for silent-error prevention |
| Output/UI consumers (`output`, CLI displays, Streamlit, PDF) | `workflows` + `api` + `clients` | These readers must consume typed `final` / `artifacts` instead of assuming mapping semantics | typed state models + external library adapters | end users | T2-P2 | Partial progress landed in output, CLI display, Streamlit display, and PDF coercion paths; remaining work is to narrow public/session dict entrypoints, remove legacy chart/table string/dict shims, and surface render failures as typed artifacts |
| Memory schema migration path | `services` + `clients` | Safely move persisted memory files from legacy dict schema to strict typed schema | persisted JSON + migration versioning | memory load/write | T2-P2 | Must support read-time migration and write-only-new-schema behavior |
| Scoped Track 2 `mypy` gate | `api/docs` + repo tooling | Add static verification for deterministic planning boundaries and stop regressions from landing unnoticed | concrete annotations in domain/services/workflows/state modules | CI / reviewers | T2-P2 | Partial progress landed: scoped `mypy` config now exists for selected deterministic modules, but the migration evidence still needs an explicit freeze-policy decision and the gate does not yet cover the broader state/workflow/tool surfaces |
| Canonical temporal/benchmark suite | `services` + `workflows` tests | Release gate for deterministic correctness | test fixtures + contracts | CI / gate review | T2-P2 | Includes failure/clarification cases |
| Repeatability tests (rerun determinism) | `services` + `workflows` tests | Prove same input => same planning output and same persisted typed-state projection | deterministic plan serialization + state serialization | CI / gate review | T2-P2 | Assert stable values, ordering, and migration-safe JSON output |
| Track docs and gate evidence | `api/docs` + `migration_evidence` | Keep implementation and gate criteria aligned | plan docs + test evidence | reviewers | T2-P3 | Update after each Track 2 milestone |

## Track 2 Boundary Rules
1. `workflows` never pass raw dicts for typed state artifacts.
2. `services` own deterministic planning and metric computation logic.
3. `domain` owns typed contract definitions and validation constraints.
4. `agents` can orchestrate but do not own deterministic comparison math.
5. Planning-path tools must enforce typed input validation at entry (no raw string-only acceptance).
6. Rank must be computed within homogeneous peer groups only: same `year`, `metric`, `dataset`, and `geo level`; missing rank grouping inputs must fail closed with `MISSING_RANK_GROUP_KEY`.
7. Typed planning nodes and contracts are reliability scaffolding for the reasoning node; they must improve reasoning-node execution quality, not bypass or replace it.
8. Temporal/benchmark/comparison nodes are early clarification gates; they do not execute the full data-retrieval/reasoning loop.
9. Reasoning node owns repeated typed Census tool invocation and downstream synthesis directives for answer/table/chart outputs.
10. Track 2 state artifacts must not be validated as Pydantic objects and then immediately downgraded back into generic `dict[str, Any]` state.
11. If serialization is required at a boundary, it must target an explicit JSON boundary only (for example persistence or external payload conversion), not an intra-graph generic dict handoff.
12. Persisted memory files may migrate schema in this track, but migration must be explicit, versioned, and fail closed on invalid legacy payloads.
13. Output/UI consumers must read typed state or use explicit adapters; they cannot silently rely on dict semantics after the state refactor.
14. A scoped static type gate should cover Track 2 boundary modules once annotations are concrete enough; if `mypy` is deferred because of the freeze rule, that deferment must be explicit in migration evidence.

## Blocked Until Later Tracks
- `EvidenceBundle` and provenance gate enforcement are Track 3.
- Dependency upgrades, FastAPI, and SSE streaming are Track 4.

## Track 2 Completion Criteria (Ownership View)
- Every Track 2 artifact has one clear owner layer.
- No planning artifact remains in mixed ownership.
- Deterministic planning path is service-owned and test-backed.
- Workflow integration preserves typed boundaries end-to-end without flattening validated state artifacts into generic dict state.
- Persistence-backed state channels use strict typed models with an explicit JSON schema migration path.
- Output/UI consumers no longer depend on dict-style access to internal state models.
- Planning-path tools enforce typed input contracts and fail closed on validation errors.
- A scoped static type gate exists for deterministic planning boundaries, or its deferment is explicitly approved and documented.
- Temporary fail-closed paths in typed contracts (including `historical_baseline`) are either fully implemented with explicit fields/validators or explicitly deferred to a later tracked milestone.
- Documentation and implementation explicitly maintain reasoning-node-first ownership: deterministic scaffolding empowers reasoning components and does not replace them.
- Workflow behavior reflects this locked principle explicitly: early planning gates feed the reasoning node; reasoning executes tool loops and output directives.
