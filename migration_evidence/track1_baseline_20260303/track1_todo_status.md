# Track 1 Todo Status (Plan Sync)

Date: 2026-03-07
Source plan: `.cursor/plans/v2-track1-structural-cleanup.plan.md`

## Todo Status

- `t1-baseline-proof`: in_progress
  - Evidence captured in `baseline_manifest.md` and test/CLI/Streamlit logs.
  - Still marked in progress because baseline parity includes known flaky integration behavior.

- `t1-boundary-map`: completed
  - Ownership decomposition map created in `ownership_decomposition_map.md`.

- `t1-move-modules`: completed
  - Structural layout moved into `src/domain`, `src/clients`, `src/services`, `src/agents`, `src/workflows`.

- `t1-fix-duplicates-paths`: completed
  - `sys.path` hacks removed from codebase.
  - Duplicate method names in `src/agents/census_query_agent.py` checked and none detected.

- `t1-doc-parity`: in_progress
  - README folder structure and key architecture paths updated.
  - Remaining doc parity verification against all architecture docs still pending.

## Remaining Track 1 Closeout

1. Final documentation parity pass (README + architecture docs).
2. Final parity re-run and evidence refresh against current refactored state.
