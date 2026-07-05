# Contract Gap Register (Track 2 - Deterministic Planning Layer)

## Purpose
Track 2 evidence artifact for enforcing typed deterministic planning contracts.
This register tracks migration from mixed/raw boundaries to strict contract-validated planning flow.

## Status Legend
- 🟢 enforced: strict typed input/output with validation and deterministic behavior checks
- 🟡 partial: contract shape exists but boundary still allows raw dict/string or non-deterministic fallback
- 🔴 missing: no typed contract enforcement yet

## Gap Table

| Boundary ID | Layer | Boundary | Current Type | Track 2 Expected Type | Status | Deterministic Risk | Track 2 Action | Evidence |
|---|---|---|---|---|---|---|---|---|
| T2-CG-001 | domain | Temporal normalization contract | heuristic parsing in mixed paths | `TemporalIntent` strict Pydantic model with explicit mode/policy enums | 🔴 | Same query can plan different year scopes | Add strict `TemporalIntent` model + validation tests | `src/domain/`, `docs/track-2_framework.md` |
| T2-CG-002 | domain | Benchmark normalization contract | implied benchmark semantics in prompts | `BenchmarkIntent` strict model with explicit comparison operator + normalization | 🔴 | Benchmark meaning can drift between runs | Add strict `BenchmarkIntent` model + validation tests | `src/domain/`, `.cursor/plans/v2-track2-deterministic-planning.plan.md` |
| T2-CG-003 | domain/services | Query plan contract | ad-hoc node/service handoffs | `ComparisonPlan` typed contract for resolved matrix/join keys/derived metrics | 🔴 | Plan shape drift causes unstable downstream compute | Add strict `ComparisonPlan` model + serialization checks | `src/services/`, `src/workflows/` |
| T2-CG-004 | workflows | Node handoff contract | `Dict[str, Any]`-heavy state transfers | typed planning objects only for Track 2 nodes | 🟢 | Hidden schema drift between nodes | Add boundary validation at each planning node | `src/workflows/`, `src/state/workflow_plan.py` |
| T2-CG-005 | services | Derived comparison math | model-assisted reasoning can influence math | deterministic service-only formulas (`difference`, `pct_difference`, `rank`, `index_base_100`) | 🟢 | Numeric outputs vary by model phrasing | Move all derived metric computation into service code + deterministic tests | `src/services/comparison_metric_compute.py` |
| T2-CG-006 | tests | Canonical temporal/benchmark acceptance | coverage exists but not canonicalized for Track 2 contracts | canonical suite asserts intent/plan structure + deterministic outcomes | 🟢 | Regressions pass without contract-level checks | Add canonical suite and block on failure | `app_test_scripts/workflow_acceptance_plans.py` |
| T2-CG-007 | tests | Repeatability guarantee | no formal repeated-input assertion for planning artifacts | repeated identical input yields identical `TemporalIntent`/`BenchmarkIntent`/`ComparisonPlan` | 🟢 | Nondeterministic plans undetected | Add rerun determinism assertions (same ordering and values) | `app_test_scripts/` |
| T2-CG-008 | governance | Dependency freeze | no explicit track gate check in artifact | explicit "no dependency change" gate in Track 2 evidence | 🟡 | Hidden dependency drift changes behavior | Add pyproject/lock manifest check before Track 2 signoff | `pyproject.toml`, `uv.lock` |

## Track 2 Decision
- Track 2 Step 1 Gate: 🟡 Partial
- Decision: **Approve with conditions**
- Condition 1: Land typed contract models before workflow wiring.
- Condition 2: Enforce deterministic service math before answer synthesis changes.
- Condition 3: Canonical suite + repeatability assertions must pass before Track 2 exit.
- Condition 4: Confirm dependency freeze at every Track 2 checkpoint.

## Exit Check Targets (Track 2)
1. `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` are strict typed contracts.
2. Planning nodes pass typed objects only and validate at boundaries.
3. Derived comparison metrics are deterministic service computations.
4. Canonical temporal/benchmark suite passes with repeated-input determinism.
5. Dependency manifest remains unchanged for this track.
