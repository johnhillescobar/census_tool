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

## Track 2 Gate Focus
- Contract consistency is currently partial (mixed typed and raw boundaries).
- Deterministic planning artifacts are not implemented yet (`TemporalIntent`, `BenchmarkIntent`, `ComparisonPlan`).
- Derived comparison math is not yet isolated into deterministic service-only paths.
- Canonical temporal/benchmark suite and repeated-input determinism checks are not yet enforced.

## Track 2 Evidence Index
- Contract gaps (Track 2): `contract_gap_register.md`
- Ownership map (Track 2): `ownership_decomposition_map.md`

## Track 2 Constraints
- No dependency upgrades in this track.
- No provenance gate enforcement changes in this track (belongs to Track 3).
- No runtime/API modernization in this track (belongs to Track 4).