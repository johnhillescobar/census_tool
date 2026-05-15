# Track 2B Closeout - Typed Workflow State

Date: 2026-05-11

## Decision

Track 2B is closed.

Track 2B closed the typed workflow-state and agent/tool boundary preservation
work needed before Track 2C/2D continue. Track 2A remains closed. Track 2C and
Track 2D remain open.

## What Changed

- Added public LangChain invocation regression coverage for planning-critical
  structured tools.
- Aligned `GeographyValidationTool`, `VariableValidationTool`, and
  `StrictCensusApiTool` with LangChain's public structured invocation path.
- Added parser-recovery contamination coverage so a prior
  `validate_geography_params` observation string fails closed instead of being
  treated as the next request's `dataset`.
- Classified remaining loose `CensusState` channels by owner and boundary type.
- Removed the artifact reducer's whole-model `model_dump()` round trip.
- Removed an unnecessary dumped-dict coercion in `WorkflowArtifactsState`
  `census_data` validation.
- Documented remaining `src/workflows/memory.py` `model_dump()` calls as Track
  2C persistence serialization boundaries, not intra-graph planning downgrades.

## Evidence Files

- Runtime failure analysis:
  `migration_evidence/track2_progress_20260511/tool_invocation_boundary_analysis.md`
- State-channel classification:
  `migration_evidence/track2_progress_20260511/track2b_state_channel_classification.md`
- Planning downgrade audit:
  `migration_evidence/track2_progress_20260511/track2b_planning_downgrade_audit.md`

## Verification

Focused failing-before evidence:

```text
uv run pytest app_test_scripts/test_track2_contract_first.py::test_planning_tools_accept_public_langchain_invoke_payloads -q
```

Initial result before tool changes:

```text
FAILED ... TypeError: GeographyValidationTool._run() got an unexpected keyword argument 'dataset'
```

Focused passing-after evidence:

```text
uv run pytest app_test_scripts/test_track2_contract_first.py::test_planning_tools_accept_public_langchain_invoke_payloads app_test_scripts/test_track2_contract_first.py::test_geography_validation_rejects_prior_observation_as_next_request -q
```

Result:

```text
2 passed
```

Track 2B regression set:

```text
uv run pytest app_test_scripts/test_track2_contract_first.py app_test_scripts/test_geography_expansion.py app_test_scripts/test_variable_validation_tool.py app_test_scripts/test_census_query_agent.py -q
```

Result:

```text
43 passed
```

## Acceptance Criteria Status

| Criterion | Status | Evidence |
|---|---|---|
| `tool.invoke({...})` passes for planning-critical structured tools | closed | `test_planning_tools_accept_public_langchain_invoke_payloads` |
| Existing direct `_run(payload)` tests still pass | closed | Track 2B regression set |
| Parser-recovery observation contamination fails closed | closed | `test_geography_validation_rejects_prior_observation_as_next_request` |
| `CensusState` loose channels are classified | closed | `track2b_state_channel_classification.md` |
| No unsafe planning-path `model_dump()` downgrade remains | closed | `track2b_planning_downgrade_audit.md` |
| Track 2A deterministic tests remain green | closed for checked subset | Track 2B regression set includes `test_track2_contract_first.py` |
| Track 2C and Track 3 scope not mixed into Track 2B | closed | persistence/provenance work remains explicitly deferred |
