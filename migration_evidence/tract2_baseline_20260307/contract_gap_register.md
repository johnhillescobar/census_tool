# Contract Gap Register (Track 2 - Strict Pydantic State Migration)

## Purpose
Track 2 evidence artifact for enforcing strict typed state and deterministic planning contracts.
This register tracks migration from mixed/raw boundaries to strict contract-validated state flow.

Review refresh: **2026-05-12**

2026-05-12 update: **Deterministic Track 2 umbrella gates 2A–2D are closed** for the
bounded scopes in their closeouts. This register remains the **live gap table**
for strict-state work: several rows are **🟡 partial** or **🔴 open** where
full-graph strictness, consumer edge cases, or incremental tightening remain.

2026-05-11 snapshot: Track 2B runtime boundary work is closed by
`migration_evidence/track2_progress_20260511/track2b_closeout.md`.

2026-05-12 update: **`T2-CG-011` moved to 🟡 partial** — Track 2E closes the bag-of-dict /
implicit JSON channel portion via `JsonMap` + workflow patch typing; textual
`dict[str, Any]` occurrences remain ratchet-controlled (see gap table row).

2026-05-04 update: the 2026-04-26 collection blocker is resolved, Streamlit
display no longer reads the previously listed dead `FinalResponseState` keys,
and the agent footnote `model_dump()` bridge is no longer present as described.
Track 2 remains partial because loose state channels (`T2-CG-011`),
non-planning strictness, **and** some governance rows were still open at the
time of that paragraph. **Governance/freeze/static-gate rows (`T2-CG-008`,
`T2-CG-010`) plus output/persistence hardening rows (`T2-CG-012`, `T2-CG-013`)
have since moved with Track 2C/2D evidence** — see table + 2026-05-12 refresh.

2026-05-04 Track 2A closeout update: rolling temporal validation is no longer
open for Track 2A. Track 2A is closed by
`migration_evidence/track2_progress_20260504/track2a_closeout.md`.

2026-05-11 update: superseded umbrella paragraph — gates 2C/2D have since closed
(`track2c_closeout.md`, `track2d_closeout.md`). Rows below supersede stale list.

## Status Legend
- 🟢 enforced: strict typed input/output with validation and deterministic behavior checks
- 🟡 partial: contract shape exists but boundary still allows raw dict/string or non-deterministic fallback
- 🔴 missing: no typed contract enforcement yet

## Gap Table

| Boundary ID | Layer | Boundary | Current Type | Track 2 Expected Type | Status | Deterministic Risk | Track 2 Action | Evidence |
|---|---|---|---|---|---|---|---|---|
| T2-CG-001 | domain | Temporal normalization contract | heuristic parsing still exists in some legacy paths, but Track 2A path now uses typed contract including `rolling_window_years` | `TemporalIntent` strict Pydantic model with explicit mode/policy/window fields | 🟢 | Reduced: typed temporal normalization now fails closed on invalid contract shapes, including rolling windows | Keep validation coverage current; broader non-planning state strictness belongs to Track 2B | `src/domain/temporal_contract.py`, `src/services/temporal_policy.py`, `app_test_scripts/test_temporal_policy_contract.py`, `migration_evidence/track2_progress_20260504/track2a_closeout.md` |
| T2-CG-002 | domain | Benchmark normalization contract | implied benchmark semantics replaced on Track 2 path by typed contract | `BenchmarkIntent` strict model with explicit comparison operator + normalization | 🟢 | Reduced: benchmark intent now validates deterministically and `historical_baseline` is fail-closed | Keep `historical_baseline` explicitly deferred or implement typed baseline fields/validators | `src/domain/benchmark_contract.py`, `src/services/benchmark_policy.py`, `app_test_scripts/test_benchmark_contract.py` |
| T2-CG-003 | domain/services | Query plan contract | service boundary emits typed `ComparisonPlan`, and the current planning path now preserves it inside `WorkflowPlanState`; remaining drift risk is downstream where other state/artifact channels stay loose | `ComparisonPlan` preserved directly inside strict Pydantic state models through workflow handoff | 🟡 | The core plan object is now typed across the planning path, but downstream loose channels can still erode guarantees once other artifacts are downgraded to generic dict/list payloads | Keep `ComparisonPlan` as the canonical plan type and finish removing dict/list downgrade points around it | `src/domain/comparison_plan.py`, `src/services/comparison_plan_policy.py`, `src/workflows/comparison.py`, `src/state/types.py`, `app_test_scripts/test_comparison_plan.py`, `app_test_scripts/test_comparison_plan_policy.py`, `app_test_scripts/test_track2_contract_first.py` |
| T2-CG-004 | workflows/state | Node handoff contract | `CensusState.plan`, `artifacts`, and `final` now have typed Pydantic envelopes, and the artifact interior is stronger than the 2026-04-07/2026-04-21 snapshots: `census_data` is now `StrictCensusApiResponse | None`, comparison rows are typed models, and `variable_labels` is typed; however, many other graph channels remain loose and some output/persistence edges still bridge back to dict payloads | strict Pydantic state channels across the graph, with no intra-graph flattening back to generic dicts | 🟡 | Hidden schema drift is reduced on the plan/final/artifact path, but loose non-planning state channels and dict-based adapters can still bypass runtime and future static checks | Extend strict state ownership beyond the current typed envelopes and remove the remaining dict/list downgrade points at output, persistence, and non-planning state boundaries | `src/state/types.py`, `src/workflows/temporal.py`, `src/workflows/benchmark.py`, `src/workflows/comparison.py`, `src/workflows/comparison_metrics.py`, `src/workflows/agent.py`, `src/workflows/output.py`, `app.py` |
| T2-CG-005 | services | Derived comparison math | deterministic service boundary now exists for supported Track 2 derived metrics | deterministic service-only formulas (`difference`, `pct_difference`, `rank`, `percentile`, `trend_gap`) | 🟢 | Reduced: numeric outputs no longer depend on model phrasing for supported metrics | Keep math in service code only and expand workflow-level evidence | `src/services/comparison_metric_compute.py`, `src/workflows/comparison_metrics.py`, `app_test_scripts/test_comparison_metric_compute.py` |
| T2-CG-011 | state | Non-planning state channels | **Track 2E (2026-05-12)**: `messages` are `ConversationMessage`; `intent/geo/candidates/profile/cache_index` plus `history` rows use `JsonMap` (recursive JSON-safe envelope) + `merge_json_maps` reducers; `CensusState` enables `validate_assignment=True`; workflow nodes emit `CensusGraphPatch.as_langgraph_update()`; memory + history writes stay on `UserMemoryFileV2` / `JsonMap` envelopes | domain-specific models beyond JSON bags where needed; retire remaining `Dict[str, Any]` ergonomics in tools/clients incrementally | 🟡 | Core state channels no longer accept silent arbitrary dict shapes without Pydantic coercion, but ~100 textual `dict[str, Any]` occurrences remain across the repo under the audit ratchet baseline | Replace JSON bags with explicit domain contracts per subsystem; tighten tool/client stubs deliberately | `src/state/types.py`, `src/domain/strict_json.py`, `src/workflows/graph_patch.py`, `src/domain/memory_persistence_contract.py`, `migration_evidence/track2_progress_20260511/track2e_raw_dict_closeout.md`, `scripts/track2_raw_dict_audit.py` |
| T2-CG-009 | tools | Planning-critical tool typed contract | `strict_census_api_call`, `validate_geography_params`, and `variable_validation` expose typed request/response contracts with `args_schema`; public LangChain `tool.invoke({...})` now passes for checked schema-shaped payloads, and prior observation strings fail closed at the geography validation boundary | planning-critical tools accept schema-shaped payloads through the public LangChain invocation path, validate them through typed contracts, and return typed validated output | 🟢 | Reduced for Track 2B: the checked runtime path no longer diverges from unit tests; remaining tool compatibility shims are documented adapters and broader async/runtime redesign belongs to later gates | Keep public invocation tests in the Track 2D verification policy; do not treat direct `_run(payload)` tests as runtime integration evidence | `src/domain/census_tool_contract.py`, `src/domain/planning_tool_contracts.py`, `src/tools/strict_census_api_tool.py`, `src/tools/geography_validation_tool.py`, `src/tools/variable_validation_tool.py`, `src/agents/census_query_agent.py`, `app_test_scripts/test_variable_validation_tool.py`, `app_test_scripts/test_track2_contract_first.py`, `migration_evidence/track2_progress_20260511/tool_invocation_boundary_analysis.md`, `migration_evidence/track2_progress_20260511/track2b_closeout.md` |
| T2-CG-006 | tests | Canonical temporal/benchmark acceptance | Track 2A service and workflow-node canonical coverage now exists and passes | canonical suite asserts intent/plan structure + deterministic outcomes | 🟢 | Reduced for Track 2A; broader e2e/state/persistence checks remain in later gates | Keep Track 2A focused suite green; broader state/output persistence testing belongs to Track 2B/2C | `app_test_scripts/test_temporal_policy_contract.py`, `app_test_scripts/test_benchmark_contract.py`, `app_test_scripts/test_comparison_plan.py`, `app_test_scripts/test_comparison_plan_policy.py`, `app_test_scripts/test_track2_contract_first.py`, `migration_evidence/track2_progress_20260504/track2a_closeout.md` |
| T2-CG-007 | tests | Repeatability guarantee | Track 2A planning rerun assertions now cover comparison-plan and rolling workflow planning outputs | repeated identical deterministic planning input yields identical planning output | 🟢 | Reduced for deterministic planning; persisted rerun coverage supplemented by Track 2C persistence regression tests (`test_memory_persistence_v2.py` subset) — extend as needed beyond current scope | Keep planning repeatability tests green | `app_test_scripts/test_comparison_plan_policy.py`, `app_test_scripts/test_track2_contract_first.py`, `migration_evidence/track2_progress_20260504/track2a_closeout.md`, `migration_evidence/track2_progress_20260511/track2c_closeout.md` |
| T2-CG-008 | governance | Dependency freeze | freeze discipline for runtime dependencies plus explicit **dev-only** tooling exception documented under Track 2D | written freeze policy distinguishing runtime deps vs documented dev tooling | 🟢 | Reduced: governance doc resolves prior manifest ambiguity | Maintain `track2d_tooling_governance.md` whenever tooling manifests change | `migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`, `migration_evidence/track2_progress_20260511/track2d_closeout.md`, `pyproject.toml`, `uv.lock` |
| T2-CG-012 | persistence | Memory schema contract | **`schema_version: 2`** artifacts (`UserMemoryFileV2`, `CacheIndexFileV2`) with legacy read migration and write-new-only serialization (Track 2C gate) | versioned persisted JSON aligned with `memory_persistence_contract` for all persisted user/cache channels | 🟡 | Remaining drift risk is confined to tightening any non-v2 payloads and fully typing adjacent loose `CensusState` channels (`T2-CG-011`) | Extend strict models wherever legacy blobs remain inconsistent with envelopes | `migration_evidence/track2_progress_20260511/track2c_closeout.md`, `src/domain/memory_persistence_contract.py`, `src/workflows/memory.py`, `src/services/memory_utils.py`, `app_test_scripts/test_memory_persistence_v2.py` |
| T2-CG-013 | api/output | Output and UI payload contract | Track 2C hardening: typed `RenderedArtifact*` unions, typed `output_node` fail-closes, quarantined chart/table coercion on `_run()` only, CLI/Streamlit/PDF ingestion improvements per `track2c_closeout.md`; legacy `_run()` string surfaces and narrowed session coercion edges retained as documented follow-ups | typed consumption or explicit adapters on every externally observable path | 🟡 | Residual shim edges are enumerated in Track 2C closeout risks rather than silent untyped successes | Narrow remaining compatibility surfaces deliberately; correlate with Track 3+ scope choices | `src/workflows/output.py`, `src/domain/rendered_output_contract.py`, `src/tools/chart_tool.py`, `src/tools/table_tool.py`, `streamlit_app.py`, `src/clients/pdf_generator.py`, `app_test_scripts/test_track2c_output_render.py`, `migration_evidence/track2_progress_20260511/track2c_closeout.md` |
| T2-CG-010 | governance/tooling | Static boundary type gate | scoped `[tool.mypy]` files plus pinned policy and dev-exception framing per Track 2D | repeatable `uv run mypy` verification on listed boundary modules under recorded policy | 🟢 | Bounded static signal on gated files; widening scope deliberately deferred | Re-run/adjust `[tool.mypy].files` when gated modules churn; widen typing under Track 4 / backlog | `migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`, `migration_evidence/track2_progress_20260511/track2d_closeout.md`, `pyproject.toml` |

## Track 2 Decision
- Track 2 Step 1 Gate: 🟢 Foundations landed (historical checkpoint)
- Deterministic umbrella **gates 2A–2D**: 🟢 **Closed** (`2026-05-04` / `2026-05-11` /
  `2026-05-12` evidence under `migration_evidence/track2_progress_*/track2*_closeout.md`).
- **Backlog scaffolding (historic “conditions”)** — cross-check against `T2-CG-*` before prioritizing:

Historical condition list (baseline snapshot):
- Condition 1 (`t2-state-models`): Replace dict-heavy state channels across most of `CensusState` with strict Pydantic models and explicit reducers/adapters.
- Condition 2 (`t2-boundary-type-preservation`): Stop creating valid Pydantic state objects and immediately dumping them back into generic dict state on the intra-graph path.
- Condition 3 (`tools typed contract`): Keep typed request/response contracts as the default planning path, prove public LangChain `tool.invoke({...})` coverage for planning-critical tools, and remove or explicitly quarantine remaining compatibility shims / loose wrappers.
- Condition 4 (`t2-mypy-boundary-gate`): Record the current `mypy` tooling decision under the Track 2 freeze rule, then expand or deliberately bound the static gate while continuing to narrow `Any` usage.
- Condition 5 (`t2-persistence-schema`): Migrate persisted memory JSON to a versioned strict schema with explicit read-time migration and write-only-new-schema behavior.
- Condition 6 (`t2-output-consumers`): Refactor CLI, Streamlit, PDF, and output helpers so they consume typed state or explicit adapters instead of dict semantics.
- Condition 7 (`t2-canonical-suite`): Add workflow-level canonical acceptance coverage before Track 2 exit.
- Condition 8 (`t2-repeatability-tests` hardening): Extend repeatability assertions beyond `ComparisonPlan` to temporal, benchmark, workflow, and persisted typed-state artifacts.
- Condition 9 (`historical_baseline` pending scope): Keep `historical_baseline` explicitly deferred or land typed baseline fields/validators.
- Condition 10 (`t2-freeze-deps` exit gate): Confirm dependency freeze again at final Track 2 signoff, including an explicit decision record for `mypy`.
- Condition 11 (`parser recovery boundary`): Prove parser recovery cannot feed a prior tool observation string into the next structured tool request.

## Recommended Next Steps
- **Track 3** — Provenance Enforcement (primary next migration focus per [`SPEC.md`](../../SPEC.md)).
- `t2-state-models`: **`T2-CG-011` Track 2E refresh (2026-05-12)** tightened non-planning `CensusState` JSON channels + LangGraph deltas — see `track2e_raw_dict_closeout.md`.
- `t2-boundary-type-preservation`: preserve validated state artifacts as typed objects; do not flatten them back into generic dicts on the intra-graph path.
- `tools typed contract`: keep schemas + public `invoke` regression coverage enforced under Track **2D** governance; tighten or retire remaining shim entry points intentionally.
- `parser recovery boundary`: add focused regression coverage around `handle_parsing_errors` and `validate_geography_params` before changing parser behavior.
- `t2-mypy-boundary-gate`: **Recorded (Track 2D)** via `track2d_tooling_governance.md`; widen coverage deliberately under Track 4 or incremental tightening.
- `t2-persistence-schema`: extend strict persisted envelopes beyond Track 2C v2 where remaining legacy blobs exist (`T2-CG-012` / `T2-CG-011`).
- `t2-output-consumers`: continue narrowing remaining shim edges enumerated in Track 2C closeout / `T2-CG-013`.
- `t2-track2-suite-refresh`: keep the fixed `app_test_scripts/test_track2_contract_first.py` import state green; 2026-05-04 evidence shows this file now collects and passes.
- `t2-census-data-source-of-truth`: make `StrictCensusApiResponse` the only accepted intra-graph `census_data` shape, then remove the remaining agent/output compatibility bridges that still normalize legacy payloads after the fact.
- `t2-canonical-suite`: replace placeholder workflow tests in `app_test_scripts/test_e2e_workflows.py` with real Track 2 canonical cases.
- `t2-repeatability-tests`: add repeated-input assertions for temporal resolution, benchmark resolution, and workflow node outputs in addition to `ComparisonPlan`.
- `historical_baseline`: either add explicit baseline contract fields/validators or mark it as intentionally deferred beyond Track 2 exit.

## Exit Check Targets (Track 2)
1. `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are strict typed contracts.
2. Most of `CensusState` is represented by strict Pydantic models with explicit reducers/adapters for graph use.
3. Workflow nodes pass typed objects only and validated state is not flattened back into generic dict state on the intra-graph path.
4. Derived comparison metrics are deterministic service computations.
5. Planning-critical tools enforce typed input/output contracts through the public LangChain invocation path and fail closed on validation errors.
6. Persisted memory files use a versioned strict schema with explicit migration from legacy payloads.
7. Output/UI consumers use typed state or explicit adapters rather than implicit dict semantics.
8. A scoped static type gate exists for Track 2 boundary modules, or its deferment is explicitly approved under the dependency-freeze rule.
9. Canonical temporal/benchmark suite passes with repeated-input determinism.
10. Dependency manifest remains unchanged for this track unless a documented tooling exception is approved.
11. Parser recovery cannot reinterpret a previous tool observation as the next structured request payload.
