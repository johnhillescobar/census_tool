# Track 2 - Deterministic Planning Ownership Map

## Scope
- Goal: Define ownership for Track 2 planning artifacts and deterministic computation path.
- Rule: Track 2 introduces planning contracts/services/workflow nodes only.
- Out of scope: provenance enforcement (Track 3), dependency/runtime modernization (Track 4).
- Layer order: `domain -> clients -> services -> agents -> workflows -> api`

## Status Legend
- `T2-P1`: implement first (contract and deterministic foundations)
- `T2-P2`: implement second (workflow integration and canonical coverage)
- `T2-P3`: implement last (refinements, docs hardening)

## Track 2 Ownership Map

| Artifact / Module | Target owner layer | Why this owner | Depends on | Used by | Priority | Notes |
|---|---|---|---|---|---|---|
| `TemporalIntent` model | `domain` | Canonical typed temporal normalization contract | Pydantic only | services, workflows | T2-P1 | Must enforce explicit mode/year/policy enums |
| `BenchmarkIntent` model | `domain` | Canonical benchmark semantics contract | Pydantic only | services, workflows | T2-P1 | Must encode comparison op + normalization mode |
| `ComparisonPlan` model | `domain` | Canonical plan object for deterministic query matrix | Pydantic only | services, workflows, agents | T2-P1 | Must carry join keys + derived metric plan |
| Temporal normalization logic | `services` | Deterministic transformation from user request to intent | domain contracts + dataset availability | workflows | T2-P1 | No model-driven math decisions |
| Benchmark planning logic | `services` | Deterministic benchmark set resolution | domain contracts + geography/data rules | workflows | T2-P1 | Must fail to clarification on unresolved benchmark |
| Query expansion logic (year x geo matrix) | `services` | Deterministic expansion from plan to API specs | domain contracts + client request DTOs | workflows | T2-P1 | Stable ordering required for repeatability |
| Derived comparison metric compute | `services` | Deterministic numeric computation boundary | API result frames + plan contract | workflows, output synthesis | T2-P1 | Never delegated to LLM text reasoning |
| Planning orchestration nodes | `workflows` | Sequence and typed handoff enforcement | services + state typing | app/workflow entry | T2-P2 | Workflows pass typed objects only |
| Workflow state typing updates | `workflows` / `state` | Preserve contract consistency across nodes | domain contracts | workflows | T2-P2 | Remove raw dict handoff for planning path |
| Canonical temporal/benchmark suite | `services` + `workflows` tests | Release gate for deterministic correctness | test fixtures + contracts | CI / gate review | T2-P2 | Includes failure/clarification cases |
| Repeatability tests (rerun determinism) | `services` + `workflows` tests | Prove same input => same planning output | deterministic plan serialization | CI / gate review | T2-P2 | Assert stable values and ordering |
| Track docs and gate evidence | `api/docs` + `migration_evidence` | Keep implementation and gate criteria aligned | plan docs + test evidence | reviewers | T2-P3 | Update after each Track 2 milestone |

## Track 2 Boundary Rules
1. `workflows` never pass raw dicts for planning artifacts.
2. `services` own deterministic planning and metric computation logic.
3. `domain` owns typed contract definitions and validation constraints.
4. `agents` can orchestrate but do not own deterministic comparison math.

## Blocked Until Later Tracks
- `EvidenceBundle` and provenance gate enforcement are Track 3.
- Dependency upgrades, FastAPI, and SSE streaming are Track 4.

## Track 2 Completion Criteria (Ownership View)
- Every Track 2 artifact has one clear owner layer.
- No planning artifact remains in mixed ownership.
- Deterministic planning path is service-owned and test-backed.
- Workflow integration preserves typed boundaries end-to-end.
