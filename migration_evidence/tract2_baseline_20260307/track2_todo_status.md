# Track 2 Todo Status (Strict State Sync)

Date: 2026-04-26
Source plans:
- `.cursor/plans/v2-track2-deterministic-planning.plan.md`
- `.cursor/plans/v2_track2_state_ab67f8f6.plan.md`

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
    - `src/workflows/agent.py` still contains legacy footnote generation that calls `result.census_data.model_dump()` for a downstream loose consumer
    - `src/workflows/output.py` now uses typed `ChartToolInput` / `TableToolInput` on the main path, but it still depends on the temporary `StrictCensusApiRawTable` adapter and has not removed the legacy-compatible tool parsers for other callers
    - `src/state/types.py` still allows loose non-planning state channels
  - Locked execution model remains unchanged: temporal/benchmark/comparison nodes are early clarification gates; reasoning node remains responsible for multi-step typed tool execution and synthesis directives.

- `migrate-persistence-schema`: pending
  - Chosen direction: allow a real JSON schema migration for persisted memory files.
  - Current persistence boundary is still legacy/untyped:
    - `src/workflows/memory.py`
    - `src/services/memory_utils.py`
    - `src/clients/file_utils.py`
  - Required outcome: read-time migration from old JSON, write-only-new-schema behavior, and explicit schema versioning.

- `update-output-consumers`: in_progress
  - Output/UI consumers are no longer all at the same baseline: CLI display and PDF now coerce typed models in key places, while Streamlit and some public compatibility wrappers still assume mapping-style `final` / `artifacts`.
  - Current evidence:
    - `src/workflows/output.py` now reads `state.final` as `FinalResponseState`, reads typed `artifacts.census_data`, uses `src/services/census_render_adapter.py`, and passes typed `ChartToolInput` / `TableToolInput` into `ChartTool.render()` / `TableTool.render()`
    - `src/domain/rendered_output_contract.py` now defines typed DTOs for narrative, footnotes, chart/table outputs, and generic rendered artifacts
    - `src/tools/table_tool.py` and `src/tools/chart_tool.py` now validate typed `StrictCensusApiRawTable` inputs internally and expose typed `render()` outputs, but their compatibility parsers plus `_run()` / `_arun()` string responses still remain for legacy callers
    - `src/api/displays.py` now coerces typed `FinalResponseState`, but `src/api/__init__.py` and `app_test_scripts/test_displays.py` still assume removed legacy display helper exports
    - `streamlit_app.py` expects dict-like `result` / `final`
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
    - `uv run pytest app_test_scripts/test_track2_contract_first.py app_test_scripts/test_census_query_agent.py app_test_scripts/test_output_title_formatting.py app_test_scripts/test_multi_series_charts.py app_test_scripts/test_pdf_generation.py -q` -> `46 passed`
    - `app_test_scripts/test_displays.py` currently fails during collection because `src.api.__init__.py` re-exports legacy display helpers that no longer exist in `src/api/displays.py`

- `t2-canonical-suite`: in_progress
  - Service/contract tests covering clarification and resolved paths are present and passing.
  - Workflow-focused Track 2 tests now exist, but full canonical acceptance coverage across workflow integration boundaries is still incomplete.

- `t2-repeatability-tests`: in_progress
  - Repeatability requirement is documented (same input -> same planning outputs).
  - `test_deterministic_rerun_same_input_same_output` now asserts identical `model_dump()` outputs from repeated `resolve_comparison_plan` calls with identical typed inputs.
  - Additional workflow-level deterministic coverage now exists for fixed comparison-metric inputs in `app_test_scripts/test_track2_contract_first.py`.
  - Gap remains: temporal, benchmark, broader workflow-level, and persisted-state rerun coverage is still incomplete.

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

1. Define strict Pydantic models for most of `CensusState`, including graph, persistence, and output-facing channels.
2. Complete workflow integration for typed handoff-only boundaries and remove remaining generic dict state artifacts from the intra-graph path, especially the agent footnote downgrade and the remaining legacy-compatible chart/table entrypoints.
3. Add explicit reducers/adapters for strict models where LangGraph merge semantics require them, then remove temporary dict/model compatibility shims from artifact merging.
4. Migrate persisted memory JSON to a versioned strict schema with explicit read-time migration.
5. Refactor CLI, Streamlit, PDF, and output helpers to typed state or explicit adapters, then switch chart/table outputs from string messages to structured rendered-artifact DTOs.
   - refinement after 2026-04-26 review: the typed render DTO path now exists on the main output flow, so the remaining work is to remove legacy `_run()` / `_arun()` string callers, align public display exports/tests, and migrate Streamlit off `final.get(...)`.
6. Reconcile the current `mypy` config/dev dependency with the Track 2 freeze rule, then expand or explicitly bound the static gate with a recorded decision.
7. Expand canonical suite to include workflow-level deterministic acceptance coverage.
8. Upgrade `BenchmarkIntent.historical_baseline` from temporary fail-closed behavior to fully typed baseline contract fields and validators.

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

## Verification Snapshot (2026-04-26 review)

- Code/state evidence checked:
  - `src/state/types.py` now shows typed `plan`, `artifacts`, and `final` envelopes
  - `src/workflows/comparison.py` preserves typed `ComparisonPlan` inside `WorkflowPlanState`
  - `src/workflows/comparison_metrics.py` now preserves typed metric rows in `WorkflowArtifactsState`
  - `src/workflows/agent.py` now writes typed `census_data` and `variable_labels` into state, but still has a loose downstream footnote bridge
  - `src/services/census_render_adapter.py` now owns the shared `StrictCensusApiResponse -> StrictCensusApiRawTable` conversion
  - `src/workflows/output.py` now consumes the shared adapter and typed variable labels, but still emits legacy dict payloads at one tool boundary
  - `src/tools/table_tool.py` and `src/tools/chart_tool.py` now validate typed raw-table inputs internally
  - `src/workflows/memory.py` still serializes `plan` / `final` at the persistence boundary
  - `pyproject.toml` now contains scoped `mypy` config plus a dev dependency entry
- Test evidence checked:
  - `app_test_scripts/test_track2_contract_first.py`
  - `app_test_scripts/test_output_title_formatting.py`
  - `app_test_scripts/test_multi_series_charts.py`
  - `app_test_scripts/test_variable_validation_tool.py`
  - `app_test_scripts/test_comparison_plan_policy.py`
- Planning decision still in force:
  - strict Pydantic state migration selected
  - JSON schema migration allowed
  - strict-everywhere outer model policy selected
