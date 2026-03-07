# Track 1 Evidence Index

## Purpose
This file maps Track 1 evidence snapshots so reviewers can quickly see:
- what was captured before structural cleanup
- what was captured after cleanup
- which folder is the latest parity evidence

## Evidence Snapshots

### `track1_baseline_20260303` (Initial baseline)
- Role: pre/posture baseline capture used to start Track 1.
- Key artifact: `baseline_manifest.md`
- Test summary in manifest: `1 failed, 135 passed, 2 skipped, 1 warning`
- Additional artifacts:
  - `ownership_decomposition_map.md`
  - `contract_gap_register.md`
  - `track1_todo_status.md`

### `track1_baseline_20260307` (Post-cleanup re-baseline)
- Role: refreshed parity evidence after Track 1 structural work.
- Key artifact: `baseline_manifest.md`
- Test summary in manifest: `1136 passed, 2 skipped, 1 warning`
- Additional artifacts:
  - `test/pytest_full_20260307.txt`
  - CLI and Streamlit run logs

## Current Source Of Truth
- Latest parity evidence folder: `track1_baseline_20260307`
- Contract gap register source: `track1_baseline_20260303/contract_gap_register.md`

## Notes
- Keeping both folders is intentional and recommended for chronology:
  - `20260303` = initial baseline snapshot
  - `20260307` = post-cleanup verification snapshot
