# Track 2 Todo Status (Strict State Sync)

Date: 2026-05-04
Source plans:
- `.cursor/plans/v2-track2-deterministic-planning.plan.md`
- `.cursor/plans/v2_track2_state_ab67f8f6.plan.md`

Refresh source:
- `migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`

## Track 2 Split

Track 2 remains the umbrella migration, but the remaining work is now grouped
into four reviewable gates:

- Track 2A - Deterministic Planning Complete: closed 2026-05-04
- Track 2B - Typed Workflow State
- Track 2C - Output, UI, And Persistence Hardening
- Track 2D - Tooling And Governance

This split is a planning aid, not a relaxation of the final Track 2 contract
rules. Full Track 2 exit still requires all four gates to close.

## Todo Status

- `t2-contracts`: done
  - `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are implemented under `src/domain`.
  - Track 2 contract expansion also landed for planning tools and final output envelopes via `src/domain/planning_tool_contracts.py` and `src/domain/final_output_contract.py`.
  - Contract-focused tests exist in `app_test_scripts/test_temporal_policy_contract.py`, `app_test_scripts/test_benchmark_contract.py`, `app_test_scripts/test_comparison_plan.py`, and `app_test_scripts/test_track2_contract_first.py`.
  - Residual issue: full end-to-end contract preservation is still incomplete because several workflow, agent, persistence, and output boundaries remain dict-heavy.

- `design-state-models`: in_progress
  - Chosen direction: strict Pydantic models across most of `CensusState`, not only the planning path.
  - Scope includes `messages`, `intent`, `geo`, `plan`, `artifacts`, `final`, `profile`, `history`, and `cache_index`.
  - Strictness choice: `extra="forbid"` style enforcement with explicit adapters where payloads drift.
  - Landed so far:
    - `src/state/types.py` now defines typed envelopes for `plan`, `artifacts`, and `final`
    - `WorkflowPlanState`, `WorkflowArtifactsState`, and `FinalResponseState` are now the current outer-model path
    - `WorkflowArtifactsState.census_data` now uses `StrictCensusApiResponse | None`
    - `WorkflowArtifactsState.comparison_input_rows` now uses `list[ComparisonInputRow]`
    - `WorkflowArtifactsState.comparison_metrics` now uses `list[ComparisonMetricRow]`
    - `WorkflowArtifactsState.variable_labels` now uses the typed `VariableLabels` contract
  - Still pending:
    - `messages`, `intent`, `geo`, `candidates`, `profile`, `history`, and `cache_index` remain loose
    - artifact merge/reducer helpers still contain temporary dict/model compatibility paths

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
    - `src/state/types.py` still allows loose non-planning state channels
  - Locked execution model remains unchanged: temporal/benchmark/comparison nodes are early clarification gates; reasoning node remains responsible for multi-step typed tool execution and synthesis directives.

- `t2-nodes-services`: done for Track 2A
  - Typed rolling temporal windows are implemented.
  - Rolling comparison plans expand deterministically through
    `LATEST_AVAILABLE_YEAR`.
  - `historical_baseline` is explicitly deferred and fail-closed.
  - Evidence: `migration_evidence/track2_progress_20260504/track2a_closeout.md`.

- `migrate-persistence-schema`: pending
  - Chosen direction: allow a real JSON schema migration for persisted memory files.
  - Current persistence boundary is still legacy/untyped:
    - `src/workflows/memory.py`
    - `src/services/memory_utils.py`
    - `src/clients/file_utils.py`
  - Required outcome: read-time migration from old JSON, write-only-new-schema behavior, and explicit schema versioning.

- `update-output-consumers`: in_progress
  - Output/UI consumers are no longer all at the same baseline: CLI display, Streamlit display, and PDF now coerce or validate typed models in key places, while public/session compatibility wrappers still accept raw dict payloads before validation.
  - Current evidence:
    - `src/workflows/output.py` now reads `state.final` as `FinalResponseState`, reads typed `artifacts.census_data`, uses `src/services/census_render_adapter.py`, and passes typed `ChartToolInput` / `TableToolInput` into `ChartTool.render()` / `TableTool.render()`
    - `src/domain/rendered_output_contract.py` now defines typed DTOs for narrative, footnotes, chart/table outputs, and generic rendered artifacts
    - `src/tools/table_tool.py` and `src/tools/chart_tool.py` now validate typed `StrictCensusApiRawTable` inputs internally and expose typed `render()` outputs, but their compatibility parsers plus `_run()` / `_arun()` string responses still remain for legacy callers
    - `src/api/displays.py` now coerces typed `FinalResponseState`, `src/api/__init__.py` now re-exports only `display_results`, and `app_test_scripts/test_displays.py` passes on that typed CLI path
    - `streamlit_app.py` now validates raw graph dicts into `CensusState` and renders typed final/artifact paths, but its public/session boundary still accepts raw dict payloads before validation
    - `src/clients/pdf_generator.py` now defines typed PDF DTOs and coerces typed `final` / `artifacts`, but its public input still accepts loose dict payloads
  - These readers are now part of the Track 2 strict-state migration surface.

- `add-regression-tests`: in_progress
  - Repeatability and fail-closed requirements are documented, and Track 2 regression coverage has expanded since the 2026-04-07 snapshot.
  - Landed so far:
    - typed workflow handoff tests
    - route coverage for typed `plan`
    - typed planning-tool contract assertions
    - typed final/artifact assertions in `agent_reasoning_node`
    - typed comparison metric assertions in `app_test_scripts/test_track2_contract_first.py`
    - focused output compatibility coverage in `app_test_scripts/test_output_title_formatting.py` and `app_test_scripts/test_multi_series_charts.py`
    - typed PDF boundary coverage in `app_test_scripts/test_pdf_generation.py`
  - Still missing:
    - memory schema migration tests
    - Streamlit and public display consumer regression tests on the typed path
    - strict validation failure tests for malformed state payloads outside the currently covered typed contracts
  - Current test reality:
    - `uv run pytest --collect-only` -> `186 tests collected`
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

- `t2-mypy-boundary-gate`: in_progress
  - `mypy` configuration is now present in `pyproject.toml`.
  - The repo now includes `mypy` in the dev dependency group and lockfile.
  - Current gap: the configured file scope is narrower than the full Track 2 state/workflow/tool surface.
  - Current policy problem: the migration evidence still needs an explicit decision record for whether this dev-only tooling change is accepted under the Track 2 dependency-freeze rule.
  - Removing remaining dict-heavy state/workflow boundaries is still higher priority than broadening the static gate.

- `t2-freeze-deps`: in_progress
  - Track constraint is documented: no dependency upgrades in Track 2.
  - Current repo state no longer matches the earlier evidence snapshot: `mypy` is now present in `pyproject.toml` and `uv.lock`.
  - This todo cannot return to `done` until the Track 2 evidence records whether that dev-only tooling addition is accepted as an explicit exception or treated as out of policy.

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

1. Define strict Pydantic models for remaining loose `CensusState` channels:
   `messages`, `intent`, `geo`, `candidates`, `profile`, `history`, and
   `cache_index`.
2. Complete workflow integration for typed handoff-only boundaries and remove
   remaining generic dict state artifacts from the intra-graph path.
3. Add explicit reducers/adapters for strict models where LangGraph merge
   semantics require them, then remove temporary dict/model compatibility shims
   from artifact merging.
4. Tighten refined agent `census_data` source-of-truth behavior so malformed
   LLM-restated data cannot outrank or block authoritative strict tool
   observations.

### Track 2C - Output, UI, And Persistence Hardening

1. Migrate persisted memory JSON to a versioned strict schema with explicit
   read-time migration.
2. Refactor CLI, Streamlit, PDF, and output helpers to typed state or explicit
   adapters at their public/session boundaries.
3. Remove legacy chart/table `_run()` / `_arun()` string callers or quarantine
   them as explicit compatibility adapters.
4. Surface render failures as typed artifacts/state instead of logs only.

### Track 2D - Tooling And Governance

1. Reconcile the current `mypy` config/dev dependency with the Track 2 freeze
   rule.
2. Expand or explicitly bound the static gate with a recorded decision.
3. Confirm final dependency-freeze status before any full Track 2 exit claim.
4. Keep migration evidence and baseline Markdown current as each gate closes.

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
  - `mypy` is now configured for selected deterministic modules, but the Track 2 evidence has not yet recorded whether that dev-only tooling addition is accepted under the freeze rule.
  - Removing generic dict state handoffs is still higher priority than broadening the `mypy` gate; otherwise the static gate will have weak signal.

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
