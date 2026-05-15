# Track 2 Todo Status (Strict State Sync)

Date: 2026-05-12
Source plans:
- `.cursor/plans/v2-track2-deterministic-planning.plan.md`
- `.cursor/plans/v2_track2_state_ab67f8f6.plan.md`

Refresh source:
- `migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`
- `migration_evidence/track2_progress_20260511/tool_invocation_boundary_analysis.md`
- `migration_evidence/track2_progress_20260511/track2b_closeout.md`
- `migration_evidence/track2_progress_20260511/track2c_closeout.md`
- `migration_evidence/track2_progress_20260511/track2d_closeout.md`
- `migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`
- `migration_evidence/track2_progress_20260511/track2e_raw_dict_closeout.md`

## Track 2 Split

Track 2 is the umbrella migration, split into four core gates (**2A–2D**) plus a
final **`Track 2E` JSON-channel closure** (see `track2e_raw_dict_closeout.md`).
**Track 2E** is also **closed**.

- Track 2A - Deterministic Planning Complete: closed 2026-05-04
- Track 2B - Typed Workflow State: closed 2026-05-11
- Track 2C - Output, UI, And Persistence Hardening: closed 2026-05-11
- Track 2D - Tooling And Governance: closed 2026-05-12
- Track 2E - Raw Dict / JSON Channel Closure: closed 2026-05-12

This split was a planning aid, not a relaxation of contract rules. **Residual
incremental tightening** (for example shrinking the `dict[str, Any]` textual surface
tracked by `scripts/track2_raw_dict_audit.py`) remains normal maintenance unless
promoted into Track **3** scope explicitly.

## Todo Status

- `t2-contracts`: done
  - `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are implemented under `src/domain`.
  - Track 2 contract expansion also landed for planning tools and final output envelopes via `src/domain/planning_tool_contracts.py` and `src/domain/final_output_contract.py`.
  - Contract-focused tests exist in `app_test_scripts/test_temporal_policy_contract.py`, `app_test_scripts/test_benchmark_contract.py`, `app_test_scripts/test_comparison_plan.py`, and `app_test_scripts/test_track2_contract_first.py`.
  - Residual issue: full end-to-end contract preservation is still incomplete because several workflow, agent, persistence, and output boundaries remain dict-heavy.

- `design-state-models`: **Track 2E complete for the JSON-channel tier** (`ConversationMessage`, `JsonMap`, `CensusGraphPatch`, coerce-on-assign on `CensusState`); optional deeper domain schemas remain backlog
  - Chosen direction: layered strictness — JSON-safe envelopes immediately, subsystem-specific contracts when payloads stabilize.
  - Scope includes `messages`, `intent`, `geo`, `plan`, `artifacts`, `final`, `profile`, `history`, and `cache_index`.
  - Strictness choice: `extra="forbid"` on outer envelopes + explicit migration helpers (`strict_json`, `memory_persistence_contract`).
  - Landed Track 2E:
    - Non-planning `CensusState` map/list channels standardized on `JsonMap` / `ConversationMessage` with validators + `merge_json_maps` profile/cache reducers (`src/state/types.py`, `src/domain/strict_json.py`).
    - LangGraph node deltas emitted through `CensusGraphPatch.as_langgraph_update()` which preserves nested Pydantic payloads for merge correctness (`src/workflows/graph_patch.py`).
    - Persisted envelopes align with typed graph channels (`memory_persistence_contract.py`, `memory_utils.py`).
  - Still pending / incremental:
    - Replace JSON bags (`JsonMap`) with richer domain models per feature area when/if needed.
    - Drive the textual `dict[str, Any]` ratchet downward (`scripts/track2_raw_dict_audit.py`).
- `migrate-workflow-readers-writers`: in_progress
  - Ownership and sequencing are documented in `ownership_decomposition_map.md`.
  - Deterministic services exist for temporal/benchmark resolution and comparison plan construction (`src/services/temporal_policy.py`, `src/services/benchmark_policy.py`, `src/services/comparison_plan_policy.py`).
  - Derived comparison metric compute service is implemented in `src/services/comparison_metric_compute.py` and wired in `src/workflows/comparison_metrics.py`.
  - Landed so far:
    - `src/workflows/temporal.py`, `src/workflows/benchmark.py`, and `src/workflows/comparison.py` now return typed plan/final envelopes on the main planning path
    - `app.py` routes via typed attribute access on `state.plan`
    - `app_test_scripts/test_track2_contract_first.py` covers typed plan preservation and typed route behavior
    - `src/workflows/comparison_metrics.py` now writes typed `ComparisonMetricRow` objects into `WorkflowArtifactsState`
    - `src/workflows/agent.py` now writes typed `result.census_data` and typed `result.variable_labels` into `WorkflowArtifactsState`
    - `src/workflows/output.py` now reads typed `artifacts.census_data`, uses a shared adapter boundary, and threads typed variable labels into chart-title generation
  - Current evidence of remaining intra-graph downgrade risk:
    - `src/workflows/agent.py` no longer contains the previously recorded footnote `model_dump()` bridge, but footnote generation still needs an explicit typed contract before this boundary can be considered closed
    - `src/workflows/output.py` now uses typed `ChartToolInput` / `TableToolInput` on the main path, but it still depends on the temporary `StrictCensusApiRawTable` adapter and has not removed the legacy-compatible tool parsers for other callers
    - `src/state/types.py` now types non-planning graph channels (`JsonMap` / `ConversationMessage`); residual risk shifts to ancillary `Dict[str, Any]` helper surfaces outside the hardened hot path (`T2-CG-011` 🟡)
  - Locked execution model remains unchanged: temporal/benchmark/comparison nodes are early clarification gates; reasoning node remains responsible for multi-step typed tool execution and synthesis directives.

- `t2-nodes-services`: done for Track 2A
  - Typed rolling temporal windows are implemented.
  - Rolling comparison plans expand deterministically through
    `LATEST_AVAILABLE_YEAR`.
  - `historical_baseline` is explicitly deferred and fail-closed.
  - Evidence: `migration_evidence/track2_progress_20260504/track2a_closeout.md`.

- `migrate-persistence-schema`: done for Track 2C (bounded gate)
  - Chosen direction: versioned migration for persisted memory files.
  - Landed: `UserMemoryFileV2` / `CacheIndexFileV2` (`schema_version: 2`) in `src/domain/memory_persistence_contract.py`; load migrates legacy blobs; writes serialize v2 (see `src/workflows/memory.py`, `src/services/memory_utils.py`).
  - Evidence: `migration_evidence/track2_progress_20260511/track2c_closeout.md`, `app_test_scripts/test_memory_persistence_v2.py`.
  - Follow-up: broader channel strictness (`T2-CG-011`) remains outside this gate’s bounded closeout where not covered by contracts above.

- `update-output-consumers`: done for Track 2C (bounded gate; follow-ups tracked in gap register / Track 3+)
  - Major evidence: typed render-success vs render-failure union, `output_node` fail-closed paths, chart/table `render()`-only typed inputs (`TypeError` otherwise), CLI/Streamlit/PDF tightened per `migration_evidence/track2_progress_20260511/track2c_closeout.md`.
  - Residual boundaries (narrowed session dict pickles, `_run()` legacy string paths, etc.) are documented as risks/follow-ups in that closeout, not reopened as unfinished Track 2C gate work.

- `add-regression-tests`: in_progress (incremental; planning + critical boundaries closed per gate docs)
  - Repeatability and fail-closed requirements are documented; Track 2 regression coverage has expanded across 2B–2D closeouts (`test_track2c_output_render.py`, `test_memory_persistence_v2.py`, etc.).
  - Landed so far:
    - typed workflow handoff tests
    - route coverage for typed `plan`
    - typed planning-tool contract assertions
    - typed final/artifact assertions in `agent_reasoning_node`
    - typed comparison metric assertions in `app_test_scripts/test_track2_contract_first.py`
    - focused output compatibility coverage in `app_test_scripts/test_output_title_formatting.py` and `app_test_scripts/test_multi_series_charts.py`
    - typed PDF boundary coverage in `app_test_scripts/test_pdf_generation.py`
  - Closed for Track 2B:
    - public LangChain `tool.invoke({...})` coverage for planning-critical tools
      that declare Pydantic `args_schema`
    - parser-recovery regression coverage proving a prior tool observation
      cannot become the next structured tool request
  - Still missing (incremental / future hardening):
    - broader Streamlit session edge-case coverage beyond Track 2C risks list
    - strict validation failure tests for malformed state payloads outside the currently covered typed contracts
  - Current test reality:
    - `uv run pytest --collect-only` -> `186 tests collected` (historical snapshot; rerun locally for current count)
    - `uv run pytest app_test_scripts/test_track2_contract_first.py` -> `7 passed`
    - `uv run pytest app_test_scripts/test_comparison_plan.py app_test_scripts/test_comparison_plan_policy.py app_test_scripts/test_comparison_metric_compute.py app_test_scripts/test_temporal_policy_contract.py` -> `20 passed`

- `t2-canonical-suite`: done for Track 2A
  - Canonical temporal, benchmark, comparison-plan, and workflow-node planning
    coverage is present and passing.
  - Evidence: `migration_evidence/track2_progress_20260504/track2a_closeout.md`.

- `t2-repeatability-tests`: done for Track 2A
  - Repeatability requirement is documented (same input -> same planning outputs).
  - `test_deterministic_rerun_same_input_same_output` now asserts identical `model_dump()` outputs from repeated `resolve_comparison_plan` calls with identical typed inputs.
  - Rolling comparison-plan rerun coverage and workflow-level rolling planning
    determinism now exist.
  - Persisted-state rerun coverage belongs to Track 2C, not Track 2A.
  - Evidence: `migration_evidence/track2_progress_20260504/track2a_closeout.md`.

- `t2-mypy-boundary-gate`: done for Track 2D (bounded static gate + recorded policy)
  - Scoped gate + dev-only `mypy` exception recorded in `migration_evidence/track2_progress_20260511/track2d_tooling_governance.md` / `track2d_closeout.md`.
  - Broader rollout remains Track 4 / incremental tightening, not unfinished Track 2D gate items.

- `t2-freeze-deps`: done for Track 2D (reconciliation recorded)
  - Runtime deps unchanged vs freeze intention; dev-only tooling exception documented; see governance doc cited above.

## Remaining Track 2 Work

### Track 2A - Deterministic Planning Complete

Status: closed 2026-05-04.

Evidence: `migration_evidence/track2_progress_20260504/track2a_closeout.md`.

Closed items:

1. `TemporalIntent` rolling-window validation is typed through
   `rolling_window_years`.
2. Rolling comparison plans expand deterministically through
   `LATEST_AVAILABLE_YEAR`.
3. Canonical temporal/benchmark/comparison tests pass at service and
   workflow-node levels.
4. Repeatability coverage exists for deterministic planning outputs.
5. `BenchmarkIntent.historical_baseline` is explicitly deferred out of Track 2A
   and fails closed.

### Track 2B - Typed Workflow State

Status: closed 2026-05-11.

Evidence: `migration_evidence/track2_progress_20260511/track2b_closeout.md`.

Closed items:

1. Remaining loose `CensusState` channels are classified by owner and boundary
   type in `track2b_state_channel_classification.md`.
2. Planning-critical structured tools now pass public LangChain
   `tool.invoke({...})` coverage.
3. Direct `_run(payload)` tests remain unit evidence, not runtime integration
   evidence.
4. Parser-recovery contamination coverage proves a
   `validate_geography_params` observation fails closed instead of becoming the
   next request's `dataset`.
5. The artifact reducer no longer round-trips the whole typed artifact model
   through `model_dump()`.
6. Remaining `src/workflows/memory.py` `model_dump()` calls are documented as
   Track 2C persistence serialization boundaries.

### Track 2C - Output, UI, And Persistence Hardening

Status: **closed `2026-05-11`**.

Evidence: [`migration_evidence/track2_progress_20260511/track2c_closeout.md`](../track2_progress_20260511/track2c_closeout.md).

Closed checklist themes (bounded scope): persisted memory **`schema_version` v2** migration + tests; typed render-success/render-failure surfaces; **`output_node`** fail-closed behavior; **`render()`-only** typed chart/table APIs with legacy coercion quarantined to `_run`/`_execute`; CLI/Streamlit/PDF tightened as documented.

Follow-up risks retained in closeout (**session pickle** one-hop coercion, legacy `_run` string paths) remain **explicit follow-ups**, not reopened Track 2C checklist debt.

### Track 2D - Tooling And Governance

Status: **closed `2026-05-12`**.

Evidence:
[`migration_evidence/track2_progress_20260511/track2d_closeout.md`](../track2_progress_20260511/track2d_closeout.md),
[`migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`](../track2_progress_20260511/track2d_tooling_governance.md).

Closed checklist themes (bounded scope): **dev-only `mypy` exception vs runtime freeze**, scoped **`[tool.mypy]`** files, **`invoke` regression policy** versus `_run` unit-only, dependency manifest reconciliation, verification commands (**pytest + `uv run mypy`**) recorded in closeout.

## Locked Policy Decisions (Track 2)

- Reasoning-node-first migration principle:
  - Canonical principle: deterministic contracts and workflow/service steps are reliability scaffolding that empower AI reasoning nodes/components and must not replace AI reasoning nodes/components.
  - Planning nodes (`temporal`, `benchmark`, `comparison`) clarify and gate ambiguous input early.
  - The reasoning node remains the execution owner, performs repeated strict typed Census tool calls as needed, and drives answer/table/chart directives.
- Boundary preservation policy:
  - A validated state artifact is not considered safe once it is flattened back into an unconstrained `dict[str, Any]`.
  - Track 2 must remove or explicitly adapt these workflow/state handoffs to prevent silent key drift and shape loss after `model_dump()`.
- Strict state policy:
  - Most of `CensusState` is targeted for strict Pydantic models, not just the planning path.
  - Internal graph state should stay typed end-to-end.
  - `model_dump()` is acceptable only at true serialization boundaries (for example persistence or explicit external payload conversion).
- Persistence migration policy:
  - Memory/profile/history/cache JSON files may change schema in this track.
  - The migration must be versioned, explicit, and fail closed on invalid legacy payloads.
- Default when no temporal phrase is present: `latest_available`.
- Temporal ambiguity policy: global.
  - If temporal signals conflict and could produce different valid plans, fail to clarification.
  - Do not auto-resolve ambiguous temporal intent.
- Agent clarification capability:
  - Agent/workflow clarification behavior may require Track 2 refactor to support deterministic fail-to-clarification outcomes.
  - Provenance gate behavior remains out of scope for Track 2 (Track 3).
- Historical baseline contract policy:
  - Current state: `historical_baseline` is fail-closed and intentionally rejected until baseline semantics are fully modeled.
  - Planned upgrade path: add explicit baseline contract fields (for example `baseline_anchor_year`, `baseline_window`) and strict validation before enabling `historical_baseline` resolution paths.
- Rank grouping policy:
  - Rank is valid only within homogeneous peer groups: same `year`, `metric`, `dataset`, and `geo level`.
  - If any required rank grouping input is missing, fail closed with `MISSING_RANK_GROUP_KEY`.
- Static type gate policy:
  - Track 2D records the scoped `mypy` gate plus a documented **dev-only** tooling exception under the freeze discipline (`migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`).
  - Widening coverage to the entire graph surface is incremental / Track 4 work unless explicitly scheduled; narrowing dict-heavy boundaries remains desirable but is **not** an unfinished Track 2D checklist item after closeout.

## Verification Snapshot (2026-05-04 review)

- Code/state evidence checked:
  - `src/state/types.py` now shows typed `plan`, `artifacts`, and `final` envelopes
  - `src/workflows/comparison.py` preserves typed `ComparisonPlan` inside `WorkflowPlanState`
  - `src/workflows/comparison_metrics.py` now preserves typed metric rows in `WorkflowArtifactsState`
  - `src/workflows/agent.py` now writes typed `census_data` and `variable_labels` into state and no longer has the previously recorded footnote `model_dump()` bridge
  - `src/services/census_render_adapter.py` now owns the shared `StrictCensusApiResponse -> StrictCensusApiRawTable` conversion
  - `src/workflows/output.py` now consumes the shared adapter and typed variable labels, uses typed `render()` calls on the main path, and guards against unsuccessful/empty Census responses before tabular derivation
  - `src/tools/table_tool.py` and `src/tools/chart_tool.py` now validate typed raw-table inputs internally, but still keep legacy parsing and string-return entrypoints for older callers
  - `src/workflows/memory.py` still serializes `plan` / `final` at the persistence boundary
  - `pyproject.toml` now contains scoped `mypy` config plus a dev dependency entry
- Test evidence checked:
  - `app_test_scripts/test_output_title_formatting.py`
  - `app_test_scripts/test_multi_series_charts.py`
  - `app_test_scripts/test_census_query_agent.py`
  - `app_test_scripts/test_pdf_generation.py`
  - `app_test_scripts/test_displays.py`
  - `app_test_scripts/test_variable_validation_tool.py`
  - `app_test_scripts/test_comparison_plan_policy.py`
- Current test evidence:
  - full pytest collection succeeds (`194 tests collected`)
  - Track 2A focused suite passes (`38 passed`)
- Planning decision still in force:
  - strict Pydantic state migration selected
  - JSON schema migration allowed
  - strict-everywhere outer model policy selected

## Verification Snapshot (2026-05-11 review)

- **Superseded for invoke failures (2026-05-12):** the three `TypeError` bullets
  below were **pre-alignment** diagnostics. Tools + tests were aligned the same
  sprint; authoritative evidence is `track2b_closeout.md` / `track2d_closeout.md`
  / `track2d_tooling_governance.md` (see **2026-05-12** snapshot below).
- New evidence checked:
  - `migration_evidence/track2_progress_20260511/tool_invocation_boundary_analysis.md`
- Targeted direct-tool evidence (historical):
  - `uv run pytest app_test_scripts/test_track2_contract_first.py::test_planning_tools_expose_strict_args_schema app_test_scripts/test_geography_expansion.py::test_geography_validation_tool_valid_params -q`
  - Result: `2 passed`
- Runtime boundary evidence (**historical pre-fix only — do not use as current truth**):
  - `GeographyValidationTool().invoke({...})` fails with
    `TypeError: GeographyValidationTool._run() got an unexpected keyword argument 'dataset'`
  - `VariableValidationTool().invoke({...})` fails with
    `TypeError: VariableValidationTool._run() got an unexpected keyword argument 'action'`
  - `StrictCensusApiTool().invoke({...})` fails with
    `TypeError: StrictCensusApiTool._run() got an unexpected keyword argument 'year'`
- Track 2B decision (still in force):
  - public LangChain tool invocation is covered for checked planning-critical structured tools
  - parser recovery around `handle_parsing_errors` has focused regression evidence at the `validate_geography_params` boundary
- Track 2D decision (still in force):
  - direct `_run(payload)` tests cannot be treated as runtime integration evidence unless corresponding public `tool.invoke({...})` coverage exists

## Verification Snapshot (2026-05-12 review)

- Gates: **2C closed** `2026-05-11` ([`track2c_closeout.md`](../track2_progress_20260511/track2c_closeout.md)); **2D closed** `2026-05-12` ([`track2d_closeout.md`](../track2_progress_20260511/track2d_closeout.md)).
- Recorded commands (from Track 2D closeout; rerun locally for sign-off):
  - `uv run pytest app_test_scripts/test_track2_contract_first.py::test_planning_tools_accept_public_langchain_invoke_payloads app_test_scripts/test_track2_contract_first.py::test_geography_validation_rejects_prior_observation_as_next_request -q`
  - `uv run mypy`
- Tooling policy source of truth: [`track2d_tooling_governance.md`](../track2_progress_20260511/track2d_tooling_governance.md).
- Next migration track: **Track 3 — Provenance Enforcement** (see [`SPEC.md`](../../SPEC.md)).
