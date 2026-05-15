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
  - superseded for Track 2A on 2026-05-04: canonical planning acceptance and repeatability coverage now close the deterministic planning gate; broader workflow/state/persistence coverage remains in later gates
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
  - superseded 2026-05-04: Streamlit display now validates typed state before rendering; remaining issue is narrower public/session dict entrypoints and compatibility-heavy wrappers
  - superseded 2026-05-04: `src/workflows/agent.py` no longer downgrades typed `census_data` with `model_dump()` when calling `footnote_generator`
  - superseded 2026-05-04: `app_test_scripts/test_track2_contract_first.py` now collects and passes
  - superseded for Track 2A on 2026-05-04: canonical planning acceptance and repeatability coverage now close the deterministic planning gate; broader workflow/state/persistence coverage remains in later gates
- Verification Evidence Checked:
  - code: `src/state/types.py`, `src/workflows/comparison_metrics.py`, `src/workflows/agent.py`, `src/workflows/output.py`, `src/services/census_render_adapter.py`, `src/tools/table_tool.py`, `src/tools/chart_tool.py`, `src/domain/rendered_output_contract.py`
  - tests: `app_test_scripts/test_track2_contract_first.py`, `app_test_scripts/test_census_query_agent.py`, `app_test_scripts/test_output_title_formatting.py`, `app_test_scripts/test_multi_series_charts.py`, `app_test_scripts/test_pdf_generation.py`
  - tests: `app_test_scripts/test_displays.py`
  - focused pytest refresh (2026-04-26): the six-file run stopped at collection because `app_test_scripts/test_track2_contract_first.py` imported removed symbol `AgentOutput`; superseded 2026-05-04 by `migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`

## Review Refresh
- Refresh Date: 2026-05-04
- Decision Update: Track 2 remains `partial`; the 2026-04-26 collection blocker and several output/UI notes are stale, but boundary, persistence, freeze-policy, and source-of-truth work remain open.
- Progress Since 2026-04-26:
  - full pytest collection succeeds (`186 tests collected`)
  - `app_test_scripts/test_track2_contract_first.py` collects and passes (`7 passed`)
  - deterministic planning/service subset passes (`20 passed`)
  - `src/workflows/agent.py` no longer contains the previously documented footnote `model_dump()` bridge
  - `streamlit_app.py` now validates `CensusState` and renders through typed `FinalResponseState` / `WorkflowArtifactsState` paths instead of reading the previously listed dead final-state keys
- Still Pending (post-2026-05-04; several items closed in Track 2C/2D — see **`2026-05-12` Review Refresh**):
  - most non-planning `CensusState` channels remain loose (`messages`, `intent`, `geo`, `candidates`, `profile`, `history`, `cache_index`)
  - `TemporalIntent` rolling mode still has placeholder validation
  - strict Census tool observations can override LLM-restated `census_data`, but direct parsed-output validation still needs tightening so malformed LLM-restated data cannot block the authoritative tool payload path
  - ~~output render failures are still logged rather than surfaced through typed failure artifacts~~ **→ closed Track 2C:** typed `RENDER_EXCEPTION` / `NO_TABULAR_DATA` artifacts ([`track2c_closeout.md`](../track2_progress_20260511/track2c_closeout.md))
  - ~~memory persistence …~~ **→ closed Track 2C (bounded):** `UserMemoryFileV2` / `CacheIndexFileV2` ([`track2c_closeout.md`](../track2_progress_20260511/track2c_closeout.md))
  - ~~the `mypy` … freeze-policy …~~ **→ closed Track 2D:** dev-only exception + scoped gate ([`track2d_tooling_governance.md`](../track2_progress_20260511/track2d_tooling_governance.md))
- Current Evidence:
  - `migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`

## Review Refresh
- Refresh Date: 2026-05-11
- **Historical diagnostics:** [`tool_invocation_boundary_analysis.md`](../track2_progress_20260511/tool_invocation_boundary_analysis.md) captured **pre-fix** gaps between `_run(payload)` coverage and real LangChain `invoke` behavior. Alignment + tests landed the same sprint; **`track2b_closeout.md` is the authoritative close** for runtime-boundary tooling.
- New Evidence linked from this sprint:
  - `migration_evidence/track2_progress_20260511/tool_invocation_boundary_analysis.md`
  - `migration_evidence/track2_progress_20260511/track2b_closeout.md`
- Track 2B **closed `2026-05-11`** with:
  - public `tool.invoke({...})` tests for checked planning-critical structured tools (`args_schema`-aligned payloads)
  - structured tool signature alignment with LangChain keyword invocation
  - parser-recovery regression coverage so a prior tool observation cannot be reinterpreted as the next structured tool request (`validate_geography_params` boundary)
  - planning downgrade audit + state-channel classification evidence cited in Track 2B closeout
- Track **2C / 2D** closures for output/persistence tooling are summarized in **`2026-05-12` Review Refresh** below (`track2c_closeout.md`, `track2d_closeout.md`).

## Review Refresh
- Refresh Date: 2026-05-12
- Decision Update: **Deterministic Track 2 umbrella gates 2A–2D are closed.** Next track: **Track 3 — Provenance Enforcement** (see [`SPEC.md`](../../SPEC.md)).
- Closure evidence (by gate):
  - 2C: [`migration_evidence/track2_progress_20260511/track2c_closeout.md`](../track2_progress_20260511/track2c_closeout.md)
  - 2D: [`migration_evidence/track2_progress_20260511/track2d_closeout.md`](../track2_progress_20260511/track2d_closeout.md) and [`track2d_tooling_governance.md`](../track2_progress_20260511/track2d_tooling_governance.md)
- Note: Original baseline run artifacts in [Run Info](#run-info) remain **2026-03-07**; this refresh updates **migration status** only.

## Track 2 Split
- Split Date: 2026-05-04
- Rationale: Track 2 expanded from deterministic planning artifacts into strict
  state, output/UI, persistence, and tooling governance. Those are related but
  not one practical finish line.
- Gates:
  - Track 2A - Deterministic Planning Complete: closed 2026-05-04
  - Track 2B - Typed Workflow State: closed 2026-05-11
  - Track 2C - Output, UI, And Persistence Hardening: closed 2026-05-11
  - Track 2D - Tooling And Governance: closed 2026-05-12
- Closed evidence:
  - 2C: [`migration_evidence/track2_progress_20260511/track2c_closeout.md`](../track2_progress_20260511/track2c_closeout.md)
  - 2D: [`migration_evidence/track2_progress_20260511/track2d_closeout.md`](../track2_progress_20260511/track2d_closeout.md)
- Rule: all four gates reviewed and closed independently; umbrella status summarized in **2026-05-12** refresh above.
- Track 2A evidence (historical):
  `migration_evidence/track2_progress_20260504/track2a_closeout.md`

## Track 2 Gate Focus *(post-closeout — 2026-05-12 + 2E refresh)*

- **Track 2 complete (2A–2D)** for bounded scope documented in respective closeouts.
- **Track 2E — raw JSON channel closure (2026-05-12)** addresses the `T2-CG-011` **bag-of-dict** surfaces on `CensusState` persistence/planning edges using `JsonMap`, `ConversationMessage`, and `CensusGraphPatch`. Residual work: replace JSON bags with richer domain models subsystem-by-subsystem and drive the `scripts/track2_raw_dict_audit.py` baseline down over time.
- **Public `tool.invoke({...})`** remains required regression evidence per [`track2d_tooling_governance.md`](../track2_progress_20260511/track2d_tooling_governance.md).

## Track 2 Evidence Index
- Contract gaps (Track 2): `contract_gap_register.md`
- Ownership map (Track 2): `ownership_decomposition_map.md`
- Todo and policy sync: `track2_todo_status.md`
- Loose dict inventory: `track2_loose_dict_inventory_20260408.md`
- Latest Track 2D governance:
  [`migration_evidence/track2_progress_20260511/track2d_closeout.md`](../track2_progress_20260511/track2d_closeout.md)

## Track 2 Constraints
- No dependency upgrades in this track.
- No provenance gate enforcement changes in this track (belongs to Track 3).
- No runtime/API modernization in this track (belongs to Track 4).
- If strict state migration requires a dev-only tooling exception (for example `mypy`), **it is explicitly recorded under Track 2D**: [`migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`](../track2_progress_20260511/track2d_tooling_governance.md)
