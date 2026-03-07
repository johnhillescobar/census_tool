# Track 1 Baseline Manifest

## Run Info
- Date: 2026-03-07
- Purpose: Track 1 Step 1 baseline parity harness
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

## Commands Executed
- `uv run pytest app_test_scripts/ -v`
- `uv run python main.py`
- `uv run streamlit run streamlit_app.py`

## Artifacts
- Tests log: `migration_evidence\track1_baseline_20260307\test\pytest_full_20260307.txt`
- CLI transcript/log: `migration_evidence\track1_baseline_20260307\cli_session_trtre_20260307_075456.txt`
- Streamlit logs/screenshots: `migration_evidence\track1_baseline_20260307\streamlit_demo_20260307_080432.txt`

## Parity Result
- Tests: 136 passed, 2 skipped, 1 warning in 378.47s (0:06:18)
- CLI flow: PASS — baseline scenario output matched expected behavior; see CLI transcript/log
- Streamlit flow: Streamlit (streamlit_app.py): PASS — baseline flow rendered and returned expected result; see streamlit logs/screenshots
- Notes: Known nondeterminism as this is an LLM graph application.
- Step 1 Status: 🟢 Complete (re-baselined on 2026-03-07 with passing parity evidence)

## Known contract risks
- Contract consistency is currently partial (mixed typed and raw boundaries).
- See `../track1_baseline_20260303/contract_gap_register.md` for audited gaps and Track 2 enforcement targets.
- Historical note (20260303 baseline): one flaky integration failure observed (`Invalid JSON input - Extra data`) in multi-state comparison test path.