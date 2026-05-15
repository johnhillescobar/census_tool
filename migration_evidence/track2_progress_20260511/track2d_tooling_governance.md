# Track 2D - Tooling And Governance (detailed notes)

Date: 2026-05-12

Companion closeout checklist: [`track2d_closeout.md`](track2d_closeout.md).

## 1. Mypy freeze-policy decision

**Decision:** Accept `mypy` as an explicit **Track 2 dev-only tooling exception**.

- Track 2 freezes **runtime dependency** churn; deterministic planning and typed boundaries remain the migration focus.
- `mypy` is declared in **`[dependency-groups]` `dev`** in [`pyproject.toml`](../../pyproject.toml), not as a `[project]` runtime dependency.
- Lockfile entries for `mypy` appear under **`[package.metadata.requires-dev]`** / **`[package.dev-dependencies]`** for this project only in [`uv.lock`](../../uv.lock).

Other dependency or runtime modernization changes remain owned by Track 4.

## 2. Scoped static gate (rationale)

**Gate definition:** Exactly the `[tool.mypy].files` list in [`pyproject.toml`](../../pyproject.toml):

- Selected **domain contracts** (`temporal_contract`, `benchmark_contract`, `comparison_plan`, Census client/tool contracts).
- Selected **deterministic services** (`temporal_policy`, `benchmark_policy`, `comparison_plan_policy`, `comparison_metric_compute`).

**Rationale:**

- These modules are pure/deterministic and drive Track 2A planning behavior; type signal is strongest here with minimal third-party impedance.
- Broader gates (`src/state/`, workflows, LangChain-heavy tools) accumulate `Any`/framework noise quickly; widening the gate without deliberate cleanup duplicates Track 4 surface area.
- `follow_imports = "silent"` keeps the gate local to listed files rather than exploding into the whole codebase.

Expansion of the gate is a **planned change**: document new paths in migration evidence before editing `files = [...]`.

## 3. `uv run mypy` result (verification record)

Executed on repo root configuration (inherits `[tool.mypy]` from `pyproject.toml`):

```text
Success: no issues found in 9 source files
```

Command: `uv run mypy`.

## 4. Public tool invocation verification policy

**Runtime boundary evidence:** Planning-critical structured tools MUST be exercised through LangChain **`tool.invoke({...})`** with schema-shaped payloads, matching the runtime path LangChain uses for structured tools.

**Canonical tests** (preferred regression surface):

- `app_test_scripts/test_track2_contract_first.py::test_planning_tools_accept_public_langchain_invoke_payloads`
- `app_test_scripts/test_track2_contract_first.py::test_geography_validation_rejects_prior_observation_as_next_request`

**Unit-only evidence:** Direct **`tool._run(payload)`** (or `_run`/`_execute` internals) validates implementation details but MUST NOT substitute for **`invoke`** when claiming the agent-loop boundary matches tests.

Historical analysis of the divergence is preserved in [`tool_invocation_boundary_analysis.md`](tool_invocation_boundary_analysis.md); the **resolution** for the three structured tools checked is documented in Track 2B closeout [`track2b_closeout.md`](track2b_closeout.md).

Verification run (Track 2D signoff excerpt):

```text
2 passed ... test_planning_tools_accept_public_langchain_invoke_payloads
          ... test_geography_validation_rejects_prior_observation_as_next_request
```

## 5. Dependency-freeze reconciliation

- **Runtime:** `[project.dependencies]` unchanged by Track 2D governance work (no bump policy in this closure).
- **Dev:** `mypy>=1.20.0` in `dependency-groups.dev` — the **only documented Track 2 exception** to strict “no new deps” tooling posture for freeze signoff purposes.
- **Track 4** owns substantive dependency bumps and modernization.
