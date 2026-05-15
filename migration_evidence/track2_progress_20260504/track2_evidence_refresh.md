# Track 2 Evidence Refresh - 2026-05-04

## Purpose

Refresh stale Track 2 migration evidence without rewriting the 2026-04-26 audit history.

This file supersedes specific findings in:

- `migration_evidence/track2_progress_20260426/drift_audit.md`
- `migration_evidence/tract2_baseline_20260307/baseline_manifest.md`
- `migration_evidence/tract2_baseline_20260307/contract_gap_register.md`
- `migration_evidence/tract2_baseline_20260307/track2_loose_dict_inventory_20260408.md`
- `migration_evidence/tract2_baseline_20260307/track2_todo_status.md`

## Commands Run

- `uv run pytest app_test_scripts/test_track2_contract_first.py --collect-only`
  - Result: 7 tests collected.
- `uv run pytest --collect-only`
  - Result: 186 tests collected.
- `uv run pytest app_test_scripts/test_track2_contract_first.py`
  - Result: 7 passed.
- `uv run pytest app_test_scripts/test_comparison_plan.py app_test_scripts/test_comparison_plan_policy.py app_test_scripts/test_comparison_metric_compute.py app_test_scripts/test_temporal_policy_contract.py`
  - Result: 20 passed.

## Findings Superseded From 2026-04-26

- N1: superseded. Pytest could not collect because
  `test_track2_contract_first.py` imported removed `AgentOutput`; the file now
  imports `AgentSolveResult`, collects, and passes.
- N2: superseded as written. The `model_dump()` dict bridge from agent to
  `footnote_generator` is no longer present; `src/workflows/agent.py` passes
  `result.census_data` directly.
- N4: superseded as written. Streamlit no longer reads the listed dead
  `FinalResponseState` keys; `streamlit_app.py` validates `CensusState` and
  renders typed `final` / `artifacts` paths.

## Findings Still Open Or Refined

- R1: still open. `app.py` still removes `checkpoints.db` on startup.
- R2: still open. Some tool `args_schema` entries remain disabled for
  compatibility in `src/tools/chart_tool.py`,
  `src/tools/geography_discovery_tool.py`, and
  `src/tools/area_resolution_tool.py`.
- R3: still open/refined. Core typed envelopes exist, but non-planning
  `CensusState` channels remain loose in `src/state/types.py`.
- R4: superseded by Track 2A closeout. `src/domain/temporal_contract.py` now
  has typed rolling-window validation.
- N3/R11: improved but not closed. Tool observation can override LLM-restated
  `census_data`, but malformed parsed `census_data` can still fail before
  authority replacement on direct validation paths in
  `src/agents/census_query_agent.py`.
- N5: still open. Output render failures are logged but not surfaced as typed
  output failure artifacts in `src/workflows/output.py`.

## Test Evidence Update

The 2026-04-26 statement "pytest can't collect" is no longer current.

Current verified state:

- Full suite collection succeeds: 194 tests collected.
- Track 2 contract-first file passes: 7 passed.
- Deterministic planning subset passes: 20 passed.
- Track 2A closeout focused suite passes: 38 passed.

This is not a full Track 2 exit. It proves the prior collection blocker is resolved and that the focused deterministic planning/service subset is currently green.

Track 2A closeout evidence is recorded in
`migration_evidence/track2_progress_20260504/track2a_closeout.md`.


## Supersession (2026-05-12)

Track **2D** closed; frozen-policy + static gate documented in
[`migration_evidence/track2_progress_20260511/track2d_closeout.md`](../track2_progress_20260511/track2d_closeout.md).
The “Track 2 Plan Impact” bullets below that still list `t2-mypy-boundary-gate`
/ `t2-freeze-deps` as **in progress** are **historical** for the 2026-05-04
snapshot only.

## Track 2 Plan Impact

- `t2-contracts`: remains completed.
- `t2-nodes-services`: remains in progress because `TemporalIntent` rolling validation is still a placeholder.
- `t2-boundary-type-preservation`: remains in progress, but blockers should be updated from stale N1/N2/N4 wording to current R3 plus refined N3/R11.
- `t2-canonical-suite`: remains in progress until workflow-level canonical acceptance is explicitly identified and gated.
- `t2-repeatability-tests`: remains in progress unless the project decides service-level repeatability is sufficient for this todo. Current evidence covers deterministic service/planning subset, not persistence or full workflow reruns.
- `t2-mypy-boundary-gate`: should be in progress because config/dependency evidence exists, but the freeze-policy decision is still undocumented.
- `t2-freeze-deps`: should be in progress, not completed, until the `mypy` dev-tooling exception is explicitly accepted or rejected.

## Track 2 Split Recommendation

The 2026-05-04 evidence shows that "Track 2" now contains several different
migration surfaces. Treat the remainder as four gates:

- Track 2A - Deterministic Planning Complete: closed 2026-05-04.
- Track 2B - Typed Workflow State: finish strict state ownership for loose
  graph channels and remove intra-graph dict downgrades except at explicit
  serialization boundaries.
- Track 2C - Output, UI, And Persistence Hardening: finish typed render
  failures, display/PDF/Streamlit adapters, chart/table compatibility cleanup,
  and versioned memory persistence.
- Track 2D - Tooling And Governance: record the `mypy` freeze-policy decision,
  set static gate scope, reconcile dependency status, and keep migration
  evidence current.

This split does not weaken the final Track 2 exit criteria. It creates
reviewable finish lines so deterministic planning can be closed without waiting
for every output, persistence, and tooling concern to be perfect.

## Recommended Next Updates

1. Keep 2026-04-26 audit as historical evidence, but mark it superseded by this refresh for N1, N2, and N4.
2. Update baseline Track 2 Markdown files so they no longer claim the Track 2 contract test cannot collect.
3. Replace old Streamlit dead-schema language with the current narrower issue: Streamlit has moved to typed state rendering, but public/session boundaries can still pass raw graph dicts that are validated at display time.
4. Replace old footnote `model_dump()` language with the current narrower issue: typed `census_data` is passed to footnotes, but the source-of-truth path in `census_query_agent.py` still needs tightening.
5. Record the `mypy` freeze decision before any Track 2 exit claim.
