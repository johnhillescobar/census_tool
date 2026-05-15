# Track 2D Closeout — Tooling And Governance

**Closed:** 2026-05-12

**Evidence (detailed):** [`track2d_tooling_governance.md`](track2d_tooling_governance.md)

## Decision

Track 2D closes the tooling/governance gap for deterministic Track 2: explicit `mypy` freeze exception, scoped static gate, invocation policy for planning-critical tools, and dependency reconciliation.

Track 4 still owns dependency upgrades and broader static typing rollout.

## Exit criteria checklist

| Criterion | Evidence |
|-----------|----------|
| `mypy` accepted or deferred as documented exception | Accepted as **dev-only**; see governance doc §1 vs runtime `[project]` deps |
| Static gate scope + rationale recorded | Governance doc §2 + `[tool.mypy].files` in `pyproject.toml` |
| `_run(payload)` ≠ runtime boundary without `invoke` | Governance doc §4 + canonical pytest names |
| Dependency manifest reconciled | Governance doc §5; runtime freeze unchanged |

## Verification commands

```shell
uv run pytest app_test_scripts/test_track2_contract_first.py::test_planning_tools_accept_public_langchain_invoke_payloads app_test_scripts/test_track2_contract_first.py::test_geography_validation_rejects_prior_observation_as_next_request -q
uv run mypy
```

**Results (recorded):** 2 passed; `Success: no issues found in 9 source files`.

## Full Track 2 gate status

- 2A: closed (see Track 2A evidence)
- 2B: closed [`track2b_closeout.md`](track2b_closeout.md)
- 2C: closed [`track2c_closeout.md`](track2c_closeout.md)
- 2D: closed — this file
