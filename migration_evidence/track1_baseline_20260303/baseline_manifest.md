# Track 1 Baseline Manifest

## Run Info
- Date: 2026-03-03
- Purpose: Track 1 Step 1 baseline parity harness
- Operator: <John Hill/JH>

## Environment
- OS: Windows 10.0.26200
- Shell: PowerShell
- Python: Python 3.12.10
- uv: uv 0.9.28

## Source Revision
- Commit SHA: cf9ee89083c663fa46d17d73169b8b941ef7d722
- Commit Date: Tue Mar 3 07:50:57 2026 -0600
- Commit Summary: cf9ee89 Tue Mar 3 07:50:57 2026 -0600 20260303 Commit

## Commands Executed
- `uv run pytest app_test_scripts/ -v`
- `uv run python main.py`
- `uv run streamlit run streamlit_app.py`

## Artifacts
- Tests log: `migration_evidence\track1_baseline_20260303\tests\pytest_full_20260303.txt`
- CLI transcript/log: `migration_evidence\track1_baseline_20260303\cli_log_20260303_070250.txt`
- Streamlit logs/screenshots: `migration_evidence\track1_baseline_20260303\streamlit_demo_20260303_070734.txt`

## Parity Result
- Tests: 1 failed, 135 passed, 2 skipped, 1 warning in 462.03s (0:07:42)
- CLI flow: PASS — baseline scenario output matched expected behavior; see CLI transcript/log
- Streamlit flow: Streamlit (streamlit_app.py): PASS — baseline flow rendered and returned expected result; see streamlit logs/screenshots
- Notes: Known nondeterminism as this is an LLM graph application.
- Step 1 Status: 🟡 Partial (baseline captured; one flaky integration failure documented)

## Known contract risks
- Contract consistency is currently partial (mixed typed and raw boundaries).
- See `contract_gap_register.md` for audited gaps and Track 2 enforcement targets.
- Baseline note: one flaky integration failure observed (`Invalid JSON input - Extra data`) in multi-state comparison test path.