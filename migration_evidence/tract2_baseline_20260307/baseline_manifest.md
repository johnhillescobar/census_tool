# Track 2 Baseline Manifest

## Run Info
- Date: 2026-03-07
- Purpose: Track 2 deterministic-planning baseline and gate setup
- Operator: <John Hill/JH>

## Environment
- OS: Windows 10.0.26200
- Shell: PowerShell
- Python: Python 3.12.10
- uv: uv 0.9.28

## Source Revision
- Commit SHA: 470824c1c1444c98e761a3055b22e4387a614782
- Commit Date: Sat Mar 7 07:27:05 2026 -0600
- Commit Summary: 470824c Sat Mar 7 07:27:05 2026 -0600 sys hacks cleanup

## Commands Executed (baseline carry-forward)
- `uv run pytest app_test_scripts/ -v`
- `uv run python main.py`
- `uv run streamlit run streamlit_app.py`

## Artifacts
- Tests log: `migration_evidence\tract2_baseline_20260307\test\pytest_full_20260307.txt`
- CLI transcript/log: `migration_evidence\tract2_baseline_20260307\cli_session_trtre_20260307_075456.txt`
- CLI app log: `migration_evidence\tract2_baseline_20260307\cli_log_20260307_075416.txt`
- Streamlit logs/screenshots: `migration_evidence\tract2_baseline_20260307\streamlit_demo_20260307_080432.txt`
- Session PDF: `migration_evidence\tract2_baseline_20260307\census_session_20260307_081231.pdf`

## Baseline Result (Track 2 Entry)
- Tests: 136 passed, 2 skipped, 1 warning in 378.47s (0:06:18)
- CLI flow: PASS — baseline scenario output matched expected behavior; see CLI transcript/log
- Streamlit flow: Streamlit (streamlit_app.py): PASS — baseline flow rendered and returned expected result; see streamlit logs/screenshots
- Notes: Known nondeterminism as this is an LLM graph application.
- Track 2 Entry Status: 🟢 Allowed (Track 1 parity evidence copied forward as starting point)

## Review Refresh
- Refresh Date: 2026-04-07
- Decision Update: Track 2 scope is now interpreted as a strict Pydantic state migration, not only typed planning artifacts.
- Scope Expansion:
  - most of `CensusState` is targeted for strict Pydantic modeling
  - workflow handoffs must stay typed end-to-end
  - `model_dump()` is allowed only at true serialization boundaries
  - persisted memory JSON schema migration is allowed for this effort
  - output/UI consumers are in scope because they currently assume dict-shaped `final` and `artifacts`
- Static Typing Update:
  - `mypy` is still not installed
  - any `mypy` adoption remains subject to the Track 2 dependency-freeze decision

## Review Refresh
- Refresh Date: 2026-04-21
- Decision Update: Track 2 remains `partial`; the repository has advanced beyond the 2026-04-07 snapshot, but the strict-state migration is still not exit-ready.
- Progress Since 2026-04-07:
  - `CensusState.plan`, `artifacts`, and `final` now use typed Pydantic envelopes in `src/state/types.py`
  - planning workflow nodes preserve typed `WorkflowPlanState` / `ComparisonPlan` objects instead of flattening those artifacts immediately on the core planning path
  - routing in `app.py` now uses typed state attribute access rather than `state.plan or {}` plus `.get(...)`
  - planning-critical geography and variable validation tools now expose strict `args_schema` models and typed response contracts
  - Track 2 regression coverage now includes typed workflow/tool assertions in `app_test_scripts/test_track2_contract_first.py`
- Still Pending:
  - most non-planning `CensusState` channels remain loose (`messages`, `intent`, `geo`, `candidates`, `profile`, `history`, `cache_index`)
  - `WorkflowArtifactsState` still carries loose payload blobs such as `census_data`, `comparison_input_rows`, and `comparison_metrics`
  - `comparison_metrics_node` still downgrades typed metric rows back to `dict` payloads
  - memory persistence is still legacy/untyped and still serializes `plan` / `final` at the JSON boundary without the versioned schema migration required for Track 2 exit
  - agent and output/UI boundaries still rely on dict-style payload access in key places (`src/workflows/agent.py`, `src/workflows/output.py`, CLI/Streamlit/PDF consumers)
  - workflow-level canonical acceptance and repeatability coverage are still incomplete outside the current planning-focused tests
- Static Typing Update:
  - `mypy` configuration is now present in `pyproject.toml`
  - `mypy` is now recorded in the repo's dev dependency group and lockfile
  - Track 2 evidence still needs an explicit decision record for whether that dev-only tooling change is accepted under the dependency-freeze rule
  - the current `mypy` scope is narrower than the full Track 2 surface and does not remove the need to eliminate remaining dict-heavy boundaries

## Review Refresh
- Refresh Date: 2026-04-26
- Decision Update: Track 2 remains `partial`; typed artifact ownership and early output-contract work have advanced, but the migration is still not exit-ready because output/UI and persistence boundaries remain mixed.
- Progress Since 2026-04-21:
  - `WorkflowArtifactsState.census_data` now uses `StrictCensusApiResponse | None`
  - `WorkflowArtifactsState.comparison_input_rows` now uses `list[ComparisonInputRow]`
  - `WorkflowArtifactsState.comparison_metrics` now uses `list[ComparisonMetricRow]`
  - `WorkflowArtifactsState.variable_labels` now uses the typed `VariableLabels` contract
  - `src/workflows/comparison_metrics.py` now preserves typed metric rows instead of downgrading them with `model_dump()`
  - `src/domain/agent_output_contract.py` and `src/workflows/agent.py` now carry and store typed `variable_labels` alongside typed `census_data`
  - `src/services/census_render_adapter.py` now provides a shared `StrictCensusApiResponse -> StrictCensusApiRawTable` adapter
  - `src/domain/rendered_output_contract.py` now defines typed DTOs for narrative, footnotes, chart/table outputs, and generic rendered artifacts
  - `src/tools/table_tool.py` and `src/tools/chart_tool.py` now validate typed `StrictCensusApiRawTable` inputs internally and share a single internal execution path across sync/async entrypoints
  - `src/workflows/output.py` now calls typed `ChartToolInput` / `TableToolInput` plus `render()` methods and normalizes the resulting `ChartOutput` / `TableOutput` DTOs into `RenderedArtifact`
  - focused output compatibility tests now pass for chart parameter/title behavior
- Still Pending:
  - most non-planning `CensusState` channels remain loose (`messages`, `intent`, `geo`, `candidates`, `profile`, `history`, `cache_index`)
  - artifact merge/reducer helpers still contain temporary dict/model compatibility paths
  - `src/workflows/output.py` now uses typed tool inputs on the main path, but tabular derivation is still limited to the temporary `StrictCensusApiRawTable` view and fail-closed handling is still incomplete for empty/invalid render inputs
  - `src/tools/chart_tool.py` and `src/tools/table_tool.py` still keep `str | dict` compatibility shims, and their LangChain `_run()` / `_arun()` entrypoints still return string success/error messages even though the typed `render()` path exists
  - memory persistence is still legacy/untyped and still serializes `plan` / `final` at the JSON boundary without the versioned schema migration required for Track 2 exit
  - the Streamlit UI path still relies on dict-style payload access, and agent/output boundaries are still mixed in key places (`streamlit_app.py`, parts of `src/workflows/agent.py`, compatibility-heavy public wrappers in `src/api/displays.py` and `src/clients/pdf_generator.py`)
  - `src/api/__init__.py` and `app_test_scripts/test_displays.py` still reference removed legacy display helpers, so the current display-focused test file does not collect
  - workflow-level canonical acceptance and repeatability coverage are still incomplete outside the current focused tests
- Verification Evidence Checked:
  - code: `src/state/types.py`, `src/workflows/comparison_metrics.py`, `src/workflows/agent.py`, `src/workflows/output.py`, `src/services/census_render_adapter.py`, `src/tools/table_tool.py`, `src/tools/chart_tool.py`, `src/domain/rendered_output_contract.py`
  - tests: `app_test_scripts/test_track2_contract_first.py`, `app_test_scripts/test_census_query_agent.py`, `app_test_scripts/test_output_title_formatting.py`, `app_test_scripts/test_multi_series_charts.py`, `app_test_scripts/test_pdf_generation.py`
  - focused pytest refresh (2026-04-26): `46 passed` across the files above; `app_test_scripts/test_displays.py` currently fails during collection because `src.api.__init__` re-exports `display_single_value`, `display_series`, `display_table`, and `display_not_census`, but `src/api/displays.py` now only defines `display_results`

## Track 2 Gate Focus
- Contract consistency remains partial because validated objects are still flattened into generic dict channels in workflow state.
- Deterministic planning artifacts exist, but end-to-end typed state preservation does not.
- Most `CensusState` channels (`messages`, `intent`, `geo`, `plan`, `artifacts`, `final`, `profile`, `history`, `cache_index`) still need explicit strict Pydantic ownership decisions.
- Output/UI helpers and memory persistence still assume dict/list payloads and therefore remain part of the Track 2 hardening surface.
- Derived comparison math is isolated into deterministic service-only paths for supported metrics, but workflow/state integration is not yet fully typed.
- Canonical temporal/benchmark suite and repeated-input determinism checks are still incomplete at full workflow/state level.

## Track 2 Evidence Index
- Contract gaps (Track 2): `contract_gap_register.md`
- Ownership map (Track 2): `ownership_decomposition_map.md`
- Todo and policy sync: `track2_todo_status.md`

## Track 2 Constraints
- No dependency upgrades in this track.
- No provenance gate enforcement changes in this track (belongs to Track 3).
- No runtime/API modernization in this track (belongs to Track 4).
- If strict state migration requires a dev-only tooling exception (for example `mypy`), that exception must be recorded explicitly rather than treated as an implicit Track 2 dependency change.