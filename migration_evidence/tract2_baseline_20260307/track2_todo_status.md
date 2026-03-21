# Track 2 Todo Status (Plan Sync)

Date: 2026-03-20
Source plan: `.cursor/plans/v2-track2-deterministic-planning.plan.md`

## Todo Status

- `t2-contracts`: done
  - `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are implemented under `src/domain`.
  - Contract-focused tests pass in `app_test_scripts/test_temporal_policy_contract.py`, `app_test_scripts/test_benchmark_contract.py`, and `app_test_scripts/test_comparison_plan.py`.

- `t2-nodes-services`: in_progress
  - Ownership and sequencing are documented in `ownership_decomposition_map.md`.
  - Deterministic services exist for temporal/benchmark resolution and comparison plan construction (`src/services/temporal_policy.py`, `src/services/benchmark_policy.py`, `src/services/comparison_plan_policy.py`).
  - Query expansion logic (`year x geo` matrix planning into `ComparisonPlan`) is implemented in `src/services/comparison_plan_policy.py`.
  - Derived comparison metric compute service is still pending (`src/services/comparison_metric_compute.py`).
  - Workflow wiring is partial: comparison node is wired, but typed handoff-only boundaries and workflow-level acceptance coverage are not complete.

- `t2-canonical-suite`: in_progress
  - Service/contract tests covering clarification and resolved paths are present and passing.
  - Full canonical acceptance coverage across workflow integration boundaries is still incomplete.

- `t2-repeatability-tests`: done
  - Repeatability requirement is documented (same input -> same planning outputs).
  - `test_deterministic_rerun_same_input_same_output` now asserts identical `model_dump()` outputs from repeated `resolve_comparison_plan` calls with identical typed inputs.

- `t2-freeze-deps`: done
  - Track constraint is documented: no dependency upgrades in Track 2.
  - Dependency manifests are currently unchanged in git status (`uv.lock` and common manifest files show no pending changes).

## Remaining Track 2 Work

1. Complete workflow integration for comparison planning with typed handoff-only boundaries (remove remaining dict-based planning artifacts in workflow path).
2. Implement deterministic derived comparison metric compute in `src/services/comparison_metric_compute.py` (no LLM math path).
3. Expand canonical suite to include workflow-level deterministic acceptance coverage.
4. Upgrade `BenchmarkIntent.historical_baseline` from temporary fail-closed behavior to fully typed baseline contract fields and validators.

## Locked Policy Decisions (Track 2)

- Default when no temporal phrase is present: `latest_available`.
- Temporal ambiguity policy: global.
  - If temporal signals conflict and could produce different valid plans, fail to clarification.
  - Do not auto-resolve ambiguous temporal intent.
- Agent clarification capability:
  - Agent/workflow clarification behavior may require Track 2 refactor to support deterministic fail-to-clarification outcomes.
  - Provenance gate behavior remains out of scope for Track 2 (Track 3).
- Historical baseline contract policy:
  - Current state (Option 1): `historical_baseline` is fail-closed and intentionally rejected until baseline semantics are fully modeled.
  - Planned upgrade (Option 2): add explicit baseline contract fields (for example `baseline_anchor_year`, `baseline_window`) and strict validation before enabling `historical_baseline` resolution paths.

## Verification Snapshot (2026-03-20)

- Command run:
  - `uv run pytest app_test_scripts/test_temporal_policy_contract.py app_test_scripts/test_benchmark_contract.py app_test_scripts/test_comparison_plan.py app_test_scripts/test_comparison_plan_policy.py -q`
- Result:
  - `23 passed in 2.28s`
