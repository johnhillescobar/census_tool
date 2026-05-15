# Track 2B Planning Downgrade Audit - 2026-05-11

## Purpose

Record the Track 2B audit for intra-graph planning-path downgrades. The goal is
to distinguish unsafe typed-state flattening from intentional LangGraph patch
envelopes and Track 2C serialization boundaries.

## Searches Checked

- `model_dump(` under `src/workflows/`
- `model_dump(` in `src/state/types.py`
- `state.artifacts[` / `state.plan[` mapping-style access under `src/workflows/`
- returned `"plan"` / `"artifacts"` graph patch keys under `src/workflows/`

## Findings

| Location | Classification | Decision |
|---|---|---|
| `src/workflows/temporal.py` | LangGraph patch envelope | Acceptable for Track 2B because the value under `"plan"` is `WorkflowPlanState`. |
| `src/workflows/benchmark.py` | LangGraph patch envelope | Acceptable for Track 2B because the value under `"plan"` is `WorkflowPlanState`. |
| `src/workflows/comparison.py` | LangGraph patch envelope | Acceptable for Track 2B because the value under `"plan"` is `WorkflowPlanState` carrying `ComparisonPlan`. |
| `src/workflows/comparison_metrics.py` | LangGraph patch envelope | Acceptable for Track 2B because the value under `"artifacts"` is `WorkflowArtifactsState`. |
| `src/workflows/agent.py` | LangGraph patch envelope | Acceptable for Track 2B because `"artifacts"` and `"final"` carry typed state objects. |
| `src/state/types.py` artifact reducer | Intra-graph typed reducer | Tightened in Track 2B to merge typed fields without whole-model `model_dump()` downgrade. |
| `src/state/types.py` null `census_data` coercion | Validation adapter | Tightened in Track 2B to attach `StrictCensusApiResponse` directly instead of its dumped dict. |
| `src/workflows/memory.py` `plan` / `final` `model_dump()` calls | Serialization boundary | Documented as Track 2C persistence work. This is not an intra-graph planning downgrade because it writes JSON memory records. |

## Current Decision

No unsafe planning-path `model_dump()` downgrade remains in the checked
workflow/state path. Remaining `model_dump()` calls under `src/workflows/memory.py`
are persistence serialization boundaries and stay open for Track 2C.
