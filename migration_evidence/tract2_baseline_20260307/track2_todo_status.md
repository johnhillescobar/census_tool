# Track 2 Todo Status (Plan Sync)

Date: 2026-07-05
Source plan: `.cursor/plans/v2-track2-deterministic-planning.plan.md`

## Todo Status

- `t2-contracts`: done
  - `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are implemented under `src/domain`.
  - Contract-focused tests pass in `app_test_scripts/test_temporal_policy_contract.py`, `app_test_scripts/test_benchmark_contract.py`, and `app_test_scripts/test_comparison_plan.py`.

- `t2-nodes-services`: done
  - Ownership and sequencing are documented in `ownership_decomposition_map.md`.
  - Deterministic services exist for temporal/benchmark resolution and comparison plan construction.
  - Query expansion logic is implemented in `src/services/comparison_plan_policy.py`.
  - Derived comparison metric compute service is implemented and wired in `src/workflows/comparison_metrics.py`.
  - Workflow integration uses typed `WorkflowPlan` handoffs across planning nodes.
  - Agent consumes typed plan context and feeds `comparison_input_rows` via builder and/or validated agent output.

- `t2-canonical-suite`: done
  - Service/contract tests and workflow acceptance runner cover clarification and resolved paths.
  - `app_test_scripts/workflow_acceptance_plans.py` includes geo, baseline, and metrics scenarios.
  - `app_test_scripts/test_track2_graph_invoke.py` exercises full graph invoke with stubbed agent.

- `t2-repeatability-tests`: done
  - Repeatability requirement is documented (same input -> same planning outputs).
  - `test_deterministic_rerun_same_input_same_output` asserts identical planning outputs.

- `t2-freeze-deps`: done
  - Track constraint is documented: no dependency upgrades in Track 2.

## Remaining Track 2 Work

None for core Track 2 exit criteria. Follow-up items outside this integration:

1. Tool input contract enforcement at planning-critical tool entry points (T2-P1 hardening).
2. Full year x geo matrix expansion to API specs (beyond year merge today).
3. Track 3 provenance / `EvidenceBundle` enforcement.

## Verification Snapshot (2026-07-05)

- Integrated branch: `cursor/track2-integrated-c46b`
- Command run:
  - `uv run pytest app_test_scripts/ -v -m "not integration"`
  - Track 2 focused suite including workflow acceptance and graph invoke tests
- Result: see `migration_evidence/tract2_baseline_20260705/test/pytest_full_20260705.txt`
