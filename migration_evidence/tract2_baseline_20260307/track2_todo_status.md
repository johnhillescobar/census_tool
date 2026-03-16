# Track 2 Todo Status (Plan Sync)

Date: 2026-03-07
Source plan: `.cursor/plans/v2-track2-deterministic-planning.plan.md`

## Todo Status

- `t2-contracts`: in_progress
  - Track 2 contract targets are documented in `contract_gap_register.md`.
  - `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are scoped but not implemented yet.

- `t2-nodes-services`: pending
  - Ownership and sequencing are documented in `ownership_decomposition_map.md`.
  - Deterministic planning services and workflow node wiring are not started.

- `t2-canonical-suite`: pending
  - Canonical suite requirements are identified from the full migration plan.
  - Track 2 canonical acceptance tests are not yet added.

- `t2-repeatability-tests`: pending
  - Repeatability requirement is documented (same input -> same planning outputs).
  - Determinism rerun assertions are not yet implemented.

- `t2-freeze-deps`: in_progress
  - Track constraint is documented: no dependency upgrades in Track 2.
  - Final dependency freeze verification check is pending for Track 2 exit.

## Remaining Track 2 Work

1. Implement strict typed contracts for temporal and benchmark planning.
2. Implement deterministic planning and comparison computation services.
3. Integrate typed planning nodes in workflows (typed handoff only).
4. Add canonical temporal/benchmark suite and repeatability assertions.
5. Verify dependency manifest unchanged before Track 2 signoff.

## Locked Policy Decisions (Track 2)

- Default when no temporal phrase is present: `latest_available`.
- Temporal ambiguity policy: global.
  - If temporal signals conflict and could produce different valid plans, fail to clarification.
  - Do not auto-resolve ambiguous temporal intent.
- Agent clarification capability:
  - Agent/workflow clarification behavior may require Track 2 refactor to support deterministic fail-to-clarification outcomes.
  - Provenance gate behavior remains out of scope for Track 2 (Track 3).
