# Track 2A Closeout - 2026-05-04

## Decision

Track 2A - Deterministic Planning Complete is closed.

This closeout covers only the original deterministic planning scope:

- `TemporalIntent`
- `BenchmarkIntent`
- `ComparisonPlan`
- deterministic temporal/benchmark/comparison planning services
- canonical temporal/benchmark/comparison tests
- repeated-input determinism for planning outputs

This does not close Track 2B, 2C, or 2D.

## Scope Decisions

- Rolling temporal requests are implemented as typed windows via
  `TemporalIntent.rolling_window_years`.
- Rolling query expansion is deterministic: the window ends at
  `LATEST_AVAILABLE_YEAR`.
- `historical_baseline` is explicitly deferred out of Track 2A and fails
  closed through clarification instead of silently resolving to an unsupported
  benchmark plan.

## Code Evidence

- `src/domain/temporal_contract.py`
  - `TemporalIntent` now owns `rolling_window_years`.
  - Rolling mode requires `rolling_window_years > 0`.
  - Non-rolling modes reject `rolling_window_years`.
- `src/services/temporal_policy.py`
  - `last/past N years` resolves to typed rolling intent with
    `rolling_window_years=N`.
- `src/services/comparison_plan_policy.py`
  - Rolling mode expands to a stable year range ending at
    `LATEST_AVAILABLE_YEAR`.
- `src/services/benchmark_policy.py`
  - Historical baseline language returns `BENCHMARK_BASELINE_DEFERRED`.
- `src/domain/benchmark_contract.py`
  - Direct `BenchmarkIntent(benchmark_type="historical_baseline")` remains
    fail-closed.
- `src/domain/clarification_templates.py`
  - Baseline deferment has an explicit clarification template.

## Test Evidence

Focused Track 2A suite:

```text
uv run pytest app_test_scripts/test_temporal_policy_contract.py app_test_scripts/test_benchmark_contract.py app_test_scripts/test_comparison_plan.py app_test_scripts/test_comparison_plan_policy.py app_test_scripts/test_track2_contract_first.py
```

Result:

```text
38 passed in 6.01s
```

Full collection:

```text
uv run pytest --collect-only
```

Result:

```text
194 tests collected in 8.44s
```

Lint check:

```text
ReadLints on edited code/test files: no linter errors found
```

## Exit Criteria Check

- Deterministic planning artifacts wired and validated: pass.
- Rolling temporal requests produce typed intents: pass.
- Rolling temporal requests expand deterministically: pass.
- `historical_baseline` is explicitly deferred and fail-closed: pass.
- Canonical temporal/benchmark/comparison cases pass at service level: pass.
- Workflow-node canonical planning case passes: pass.
- Repeated deterministic planning inputs produce identical outputs: pass.

## Remaining Track 2 Work Outside 2A

- Track 2B: loose non-planning `CensusState` channels and broader typed state
  preservation.
- Track 2C: output failure DTOs, UI/public compatibility adapters, and
  versioned memory persistence.
- Track 2D: `mypy` freeze-policy decision and static gate scope.
