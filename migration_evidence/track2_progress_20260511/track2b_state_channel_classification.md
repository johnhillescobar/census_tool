# Track 2B State Channel Classification - 2026-05-11

## Purpose

Classify the remaining loose `CensusState` channels for Track 2B. This is not a
Track 2C persistence or UI migration plan; it defines which channels must be
tightened now and which are intentionally left to later gates.

## Classification

| Channel | Current shape | Track 2B owner | Boundary type | Track 2B decision |
|---|---|---|---|---|
| `messages` | `list[dict[str, Any]]` | agent/workflow boundary | external LangChain message wire format | Leave as an explicit external/session wire format for Track 2B; do not use it for typed planning artifacts. |
| `intent` | `dict[str, Any] \| None` | agent/workflow boundary | planning-adjacent legacy intent map | Keep as a Track 2B typed-state candidate; do not expand in this pass because agent intent production still uses legacy dict semantics. |
| `geo` | `dict[str, Any]` | workflow/agent boundary | planning-adjacent legacy geography map | Keep as a Track 2B typed-state candidate; restrict new planning work to typed tool contracts until geo ownership is modeled. |
| `candidates` | `dict[str, Any]` | workflow/services boundary | planning-adjacent variable candidate map | Keep as a Track 2B typed-state candidate; no new generic candidate payloads should be added. |
| `plan` | `WorkflowPlanState \| None` | state/workflows | typed workflow state | Already typed for Track 2B. |
| `artifacts` | `WorkflowArtifactsState` | state/workflows | typed workflow state with reducer | Track 2B tightened reducer to merge typed fields without whole-model dict downgrade. |
| `final` | `FinalResponseState \| None` | state/workflows | typed workflow state | Already typed for Track 2B. |
| `profile` | `dict[str, Any]` | services/clients | persisted memory wire format | Leave to Track 2C versioned persistence migration. |
| `history` | `list[dict[str, Any]]` | services/clients | persisted memory wire format | Leave to Track 2C versioned persistence migration. |
| `cache_index` | `dict[str, Any]` | services/clients | persisted cache wire format | Leave to Track 2C versioned persistence migration. |

## Track 2B Closure Rule

Track 2B can close if typed planning artifacts and planning-critical tool
payloads are preserved across runtime boundaries. It does not require finishing
the Track 2C persistence schema migration, but it must not mislabel
profile/history/cache dicts as typed workflow state.

## Evidence Links

- Parent plan:
  `.cursor/plans/v2-track2-deterministic-planning.plan.md`
- Tool boundary analysis:
  `migration_evidence/track2_progress_20260511/tool_invocation_boundary_analysis.md`
- Loose dict inventory:
  `migration_evidence/tract2_baseline_20260307/track2_loose_dict_inventory_20260408.md`
