# Contract Gap Register (Track 1 - Structural Cleanup)

## Purpose
Track 1 evidence artifact for contract consistency audit.
No behavior changes are made in this track; this register identifies where to enforce typed contracts in Track 2.

## Status Legend
- 🟢 typed: input/output validated with Pydantic model
- 🟡 partial: model exists but boundary still accepts raw dict/string
- 🔴 raw: no strict validation at boundary

## Gap Table

| Boundary ID | Layer | Boundary | Current Type | Expected Type | Status | Risk | Track Action | Evidence |
|---|---|---|---|---|---|---|---|---|
| CG-001 | tools | `geography_discovery` `_run(tool_input)` | `str` + `json.loads` | `GeographyDiscoveryInput` model-validated input | 🔴 | JSON parse errors can break flow nondeterministically | T1-log-only, T2-hard-enforce | `src/tools/geography_discovery_tool.py` |
| CG-002 | tools | `resolve_area_name` `_run(tool_input)` | `str` + `json.loads` | `AreaResolutionInput` model-validated input | 🔴 | malformed tool payloads return string errors, not typed failures | T1-log-only, T2-hard-enforce | `src/tools/area_resolution_tool.py` |
| CG-003 | tools | `variable_validation` `_run` | mixed string/dict handling | strict typed request + typed response model | 🟡 | inconsistent caller behavior accepted silently | T1-log-only, T2-hard-enforce | `src/tools/variable_validation_tool.py` |
| CG-004 | tools | `geography_validation` `_run` | mixed string/dict handling | strict typed request + typed response model | 🟡 | invalid JSON can surface late in agent parse | T1-log-only, T2-hard-enforce | `src/tools/geography_validation_tool.py` |
| CG-005 | agent | agent final output parse | free-text parse + JSON extraction | strict `AgentOutput` contract at boundary | 🟡 | LLM formatting drift causes intermittent failures | T1-log-only, T2-hard-enforce | `src/utils/agents/census_query_agent.py` |
| CG-006 | workflows | node -> state handoff | `Dict[str, Any]` fields in state | typed workflow contracts (`TemporalIntent`, etc. in Track 2) | 🟡 | schema drift between nodes | T1-log-only, T2-hard-enforce | `src/state/types.py`, `src/nodes/agent.py` |
| CG-007 | integration tests | live LLM/tool integration | real API + nondeterministic output | deterministic contract tests + separate live smoke tests | 🟡 | flaky baseline can mask regressions | T1-doc + T2-test split | `app_test_scripts/test_integration_agent_api.py` |

## Known Observations (Baseline Run 2026-03-03)
- One integration failure observed in multi-state comparison path.
- Error signature includes `Invalid JSON input - Extra data`.
- This indicates contract enforcement is not fail-closed at all boundaries.

## Track 1 Decision
- Track 1 Step 1 Gate: 🟡 Partial
- Decision: **Approve with conditions**
- Condition 1: Keep this register updated for every moved module/boundary.
- Condition 2: Do not introduce runtime behavior changes in Track 1.
- Condition 3: Promote all 🔴/🟡 items to T2 implementation backlog before Track 2 exit.

## Track 2 Enforcement Targets (Planned)
1. Enable strict typed tool input schemas at all tool boundaries.
2. Enforce typed tool output objects (no raw error strings).
3. Enforce typed node/workflow state transfer objects.
4. Fail-closed on validation errors with explicit structured error models.