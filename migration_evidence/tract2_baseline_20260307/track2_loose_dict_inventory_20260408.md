# Track 2 Loose Dict Inventory

Date: 2026-04-08

Refresh: 2026-05-04. Stale 2026-04-26 notes about the Track 2 contract test
collection blocker, Streamlit dead-schema rendering, and the agent footnote
`model_dump()` bridge have been superseded by
`migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`.

## Purpose
- Enumerate the remaining runtime `Dict[...]`, `dict[...]`, `List[Dict[...]]`, and `list[dict[...]]` boundaries that still weaken Track 2.
- Separate real Track 2 blockers from temporary adapters and acceptable map-shaped payloads.
- Stop rediscovering the same loose fields during repeated review passes.

## Scope
- Included: runtime Python in `src/`, `main.py`, and `streamlit_app.py`.
- Excluded: tests, notebooks, docs/examples, and historical evidence files.

## Classification
- `blocking_any_dict`: must be replaced before Track 2 can honestly be called contract-complete.
- `temporary_adapter`: compatibility shim that may exist briefly, but should not be treated as the steady-state design.
- `acceptable_map`: narrow map-shaped value object or wire-format payload that can remain dict-shaped if explicitly owned.

## Inventory

### State core

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/state/types.py` | `_merge_dict()` | `Dict[str, Any]` | `blocking_any_dict` | Generic reducer for `profile` and `cache_index`. |
| `src/state/types.py` | `_merge_artifacts()` | merges typed models via `model_dump()` dicts | `temporary_adapter` | Typed shell exists, but merge logic still round-trips through dict. |
| `src/state/types.py` | `_coerce_artifacts()` | accepts `WorkflowArtifactsState \| Dict[str, Any] \| None` | `temporary_adapter` | Explicit dict-or-model escape hatch remains. |
| `src/state/types.py` | `WorkflowArtifactsState.census_data` | `StrictCensusApiResponse \| None` | removed from blocker list | No longer a loose blob at state entry; remaining issue is the temporary optional migration shape. |
| `src/state/types.py` | `WorkflowArtifactsState.comparison_input_rows` | `list[ComparisonInputRow]` | removed from blocker list | No longer loose at state entry. |
| `src/state/types.py` | `WorkflowArtifactsState.comparison_metrics` | `list[ComparisonMetricRow]` | removed from blocker list | No longer loose at state entry. |
| `src/state/types.py` | `WorkflowArtifactsState.variable_labels` | `VariableLabels` | removed from blocker list | Typed variable metadata contract now exists in workflow state. |
| `src/state/types.py` | `CensusState.messages` | `List[Dict[str, Any]]` | `blocking_any_dict` | Chat messages have no declared schema. |
| `src/state/types.py` | `CensusState.intent` | `Dict[str, Any] \| None` | `blocking_any_dict` | Intent remains a blob. |
| `src/state/types.py` | `CensusState.geo` | `Dict[str, Any]` | `blocking_any_dict` | Geo state remains a blob. |
| `src/state/types.py` | `CensusState.candidates` | `Dict[str, Any]` | `blocking_any_dict` | Candidate variable state has no schema. |
| `src/state/types.py` | `CensusState.profile` | `Dict[str, Any]` | `blocking_any_dict` | Persisted profile is schema-less. |
| `src/state/types.py` | `CensusState.history` | `List[Dict[str, Any]]` | `blocking_any_dict` | History records are schema-less. |
| `src/state/types.py` | `CensusState.cache_index` | `Dict[str, Any]` | `blocking_any_dict` | Cache metadata has no strict schema. |
| `src/state/types.py` | `QuerySpec.geo` | `Dict[str, Any]` | `blocking_any_dict` | Query geo filters are still loose. |
| `src/state/types.py` | `GeographyEntity.context` | `Dict[str, Any]` | `blocking_any_dict` | Open-ended context bag. |
| `src/state/types.py` | `ResolvedGeography.geocoding_metadata` | `Dict[str, Any]` | `temporary_adapter` | Provider metadata may stay adapter-owned temporarily. |
| `src/state/types.py` | `ResolvedGeography.filters` | `Dict[str, str]` | `acceptable_map` | Legitimate Census filter map. |
| `src/state/types.py` | `ResolvedGeography.fips_codes` | `Dict[str, str]` | `acceptable_map` | Legitimate FIPS code map. |

### Workflow and graph handoffs

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/workflows/temporal.py` | `temporal_node()` | returns `dict[str, Any]` | `temporary_adapter` | Envelope is dict-shaped, payloads are mostly typed. |
| `src/workflows/benchmark.py` | `benchmark_node()` | returns `dict[str, Any]` | `temporary_adapter` | Same issue. |
| `src/workflows/comparison.py` | `comparison_node()` | returns `dict[str, Any]` | `temporary_adapter` | Same issue. |
| `src/workflows/comparison_metrics.py` | `comparison_metrics_node()` | returns `dict[str, Any]` | `temporary_adapter` | Same issue. |
| `src/workflows/agent.py` | `agent_reasoning_node()` | returns `Dict[str, Any]` | `temporary_adapter` | Envelope is still dict-shaped, but typed `WorkflowArtifactsState` / `FinalResponseState` payloads are now used inside it. |
| `src/workflows/agent.py` | footnote generation boundary | typed `result.census_data` passed directly to downstream consumer | `temporary_adapter` | The previously recorded `model_dump()` bridge is gone; keep watching this boundary until footnote generation has an explicit typed input/output contract. |
| `src/workflows/output.py` | `get_chart_params(raw_data: StrictCensusApiRawTable \| Dict[str, Any], ...)` | typed input plus legacy dict fallback | `temporary_adapter` | Main path is typed now; dict fallback remains for compatibility and existing tests. |
| `src/workflows/output.py` | `output_node()` | returns `Dict[str, Any]` | `temporary_adapter` | Envelope is dict-shaped. |
| `src/workflows/output.py` | `_response_to_tabular_payload()` | typed raw table converted back to legacy dict payload | `temporary_adapter` | Output path still bridges typed render data back to old tool shape. |
| `src/workflows/memory.py` | `memory_load_node()` | returns `Dict[str, Any]` | `blocking_any_dict` | Untyped persisted payloads re-enter state directly. |
| `src/workflows/memory.py` | `memory_write_node()` | returns `Dict[str, Any]` | `blocking_any_dict` | Persists typed state after flattening to loose JSON. |

### UI and entry points

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/api/displays.py` | `display_results()` public wrapper | `Dict[str, Any]` outer result plus typed `FinalResponseState` coercion | `temporary_adapter` | CLI display now validates/coerces `final`, but the public wrapper is still dict-shaped and stale exports/tests still target removed legacy helpers. |
| `streamlit_app.py` | `display_streamlit_results()` and helpers | `CensusState \| dict[str, Any] \| None` | `temporary_adapter` | Display now validates raw graph dicts into `CensusState` and renders typed final/artifact paths; public/session entry still accepts raw dict payloads before validation. |
| `streamlit_app.py` | `process_question()` | returns `Dict[str, Any]` | `blocking_any_dict` | Graph output stored and passed around as loose dict. |
| `streamlit_app.py` | `initial_state = CensusState(... geo={}, artifacts={}, profile={} ...)` | raw dict initialization | `blocking_any_dict` | Entry point seeds loose state bags directly. |
| `main.py` | `initial_state = CensusState(... geo={}, artifacts={}, profile={} ...)` | raw dict initialization | `blocking_any_dict` | CLI does the same. |
| `src/clients/pdf_generator.py` | `generate_session_pdf()` public input | loose entry payloads coerced into typed PDF DTOs | `temporary_adapter` | PDF path now defines `PdfConversationEntry`, `PdfConversationResult`, and `PdfSessionMetadata`, but the public entry still accepts dict payloads for compatibility. |

### Tools

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/tools/strict_census_api_tool.py` | strict request -> legacy dict wrapper | `result.get(...)` on dict payload | `blocking_any_dict` | Supposedly strict path still depends on loose client wrapper. |
| `src/tools/census_api_tool.py` | `_run(tool_input: str)` + JSON parse + `.get(...)` | loose legacy tool path | `blocking_any_dict` | Parallel untyped path still exists. |
| `src/tools/chart_tool.py` | `ChartToolInput.data` | `StrictCensusApiRawTable` | removed from blocker list | Tool input is typed now; legacy compatibility lives in parse/coercion helpers instead. |
| `src/tools/chart_tool.py` | `_parse_input()` / `_coerce_legacy_table_data()` | typed input plus `str | dict` compatibility | `temporary_adapter` | ReAct-era compatibility shim still present. |
| `src/tools/table_tool.py` | `TableToolInput.data` | `StrictCensusApiRawTable` | removed from blocker list | Tool input is typed now; legacy compatibility lives in parse/coercion helpers instead. |
| `src/tools/table_tool.py` | `_parse_input()` / `_coerce_legacy_table_data()` | typed input plus `str | dict` compatibility | `temporary_adapter` | ReAct-era compatibility shim still present. |
| `src/tools/geography_validation_tool.py` | `GeographyValidationRequest \| str \| dict[str, Any]` | typed contract plus shim | `temporary_adapter` | Dict/string input still accepted for compatibility. |
| `src/tools/variable_validation_tool.py` | `VariableValidationRequest \| str \| dict[str, Any]` | typed contract plus shim | `temporary_adapter` | Same issue. |
| `src/tools/pattern_builder_tool.py` | JSON string parsing + `.get(...)` | loose tool input | `blocking_any_dict` | Still planning-adjacent and untyped. |
| `src/tools/geography_discovery_tool.py` | disabled `args_schema`, JSON string parsing | loose tool input | `temporary_adapter` | ReAct-compatibility shim. |
| `src/tools/geography_hierarchy_tool.py` | JSON parse then manual response dict | partial adapter | `temporary_adapter` | Typed input is incomplete, response remains manual dict/json. |
| `src/tools/table_validation_tool.py` | JSON string parsing | loose tool input | `temporary_adapter` | Legacy compatibility path. |
| `src/tools/json_parse.py` | `parse_first_json() -> Any` | untyped parser | `temporary_adapter` | Compatibility helper while string-based tools remain. |

### Clients

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/clients/census_api_utils.py` | `geo: dict[str, Any]` in multiple helpers | loose geo contract | `blocking_any_dict` | Typed client utilities still accept generic geo blobs. |
| `src/clients/census_api_utils.py` | `fetch_census_data() -> dict[str, Any]` | backward-compatible dict wrapper | `blocking_any_dict` | Legacy wrapper still exists under strict paths. |
| `src/clients/census_api_utils.py` | `table_metadata: dict[str, Any]` | loose metadata contract | `blocking_any_dict` | Table metadata remains schema-less. |
| `src/clients/census_api_utils.py` | `_query_params_payload() -> dict[str, str]` | HTTP query payload | `acceptable_map` | Legitimate wire-format map. |
| `src/clients/census_api_utils.py` | `build_geo_filters() -> dict[str, str]` | encoded `for` / `in` payload | `acceptable_map` | Legitimate wire-format map. |
| `src/clients/telemetry.py` | `record_event(..., payload: Dict[str, Any])` | generic event payload | `acceptable_map` | Telemetry is intentionally event-shaped and open-ended. |

### Agents

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/agents/census_query_agent.py` | `_build_empty_output_response()` | returns `Dict[str, Any]` | `blocking_any_dict` | Fallback output payload is built as a generic dict. |
| `src/agents/census_query_agent.py` | `_build_iteration_limit_response()` | returns `Dict[str, Any]` | `blocking_any_dict` | Same issue. |
| `src/agents/census_query_agent.py` | `_coerce_observation_to_dict()` | `Dict[str, Any] \| None` | `temporary_adapter` | Intermediate shim for tool observations. |
| `src/agents/census_query_agent.py` | `_normalize_parsed_output_contract()` | `Dict[str, Any] -> Dict[str, Any]` | `temporary_adapter` | Contract drift shim before validation. |
| `src/agents/census_query_agent.py` | `charts_needed`, `tables_needed` | typed `FinalChartSpec` / `FinalTableSpec` via `AgentSolveResult` | removed from blocker list | Output intent models are no longer raw inner dicts at the solved-result boundary. |

### Services

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/services/memory_utils.py` | `build_history_record()` inputs and return | `Dict[str, Any]` | `blocking_any_dict` | History persistence schema is loose. |
| `src/services/memory_utils.py` | `update_profile()` inputs and return | `Dict[str, Any]` | `blocking_any_dict` | Profile persistence schema is loose. |
| `src/services/conversation_summarizer.py` | `truncate_messages_by_tokens(messages: List[Dict[str, Any]], ...)` | loose message list | `blocking_any_dict` | Transcript shape is still implicit. |
| `src/services/enumeration_detector.py` | `intent: Dict[str, Any] \| None` | loose intent input | `blocking_any_dict` | Planning helper still consumes intent blob. |
| `src/services/enumeration_detector.py` | `build_enumeration_filters(...) -> Dict[str, Any]` | loose filter result | `blocking_any_dict` | Output should become a typed geo/filter model. |
| `src/services/variable_validator.py` | catalog helpers and normalized metadata | mixed `Dict` usage | `temporary_adapter` | Mostly API catalog normalization; lower priority unless full catalog typing is required. |

### Domain and LLM helpers

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/domain/geo_utils.py` | `_mapping_entry()`, `DEFAULT_GEO`, `resolve_default_geo()` | `Dict[str, Any]` | `blocking_any_dict` | Core geo defaults still use loose maps. |
| `src/domain/geo_utils.py` | `GEOGRAPHY_MAPPINGS` | `Dict[str, Dict[str, Any]]` | `blocking_any_dict` | Central geo config still hides shape behind `Any`. |
| `src/domain/geography_registry.py` | multiple helpers returning `Dict[str, Dict[str, Any]]` or `Dict[str, Any] \| None` | loose geo resolution contracts | `blocking_any_dict` | Registry remains heavily dict-shaped. |
| `src/domain/text_utils.py` | multiple helpers using `intent`, `geo`, `previews`, `datasets` as `Dict[str, Any]` | loose domain handoffs | `blocking_any_dict` | Retrieval and text generation still depend on blobs. |
| `src/domain/census_groups.py` | `fetch_groups_list(...) -> List[Dict]` | loose external payload | `temporary_adapter` | External API list remains untyped. |
| `src/llm/intent_enhancer.py` | `user_profile`, `heuristic_intent`, `llm_intent`, `artifacts`, `geo`, `intent` as `Dict[str, Any]` | loose LLM helper contracts | `blocking_any_dict` | Planning-related LLM helper still uses blobs. |
| `src/llm/category_detector.py` | multiple `Dict[str, Any]` result/response shapes | loose retrieval helper contracts | `temporary_adapter` | Lower Track 2 priority unless this path is considered deterministic planning scope. |
| `src/llm/factory.py` | `openai_params`, `anthropic_params` | `dict[str, Any]` | `acceptable_map` | Provider kwargs are true client call parameter bags. |

### Already strict or acceptably map-shaped

| File | Symbol / field | Current shape | Class | Notes |
|---|---|---|---|---|
| `src/domain/planning_tool_contracts.py` | `geo_for`, `geo_in`, `source` | `dict[str, str]` | `acceptable_map` | Narrow contract-owned maps, not `Any` blobs. |
| `src/domain/census_tool_contract.py` | `geo_for`, `geo_in`, `geo_in_chained`, `values` | `dict[str, str]`, `list[dict[str, str]]` | `acceptable_map` | Narrow value maps owned by explicit Pydantic contracts. |
| `src/domain/census_client_contract.py` | `to_records() -> list[dict[str, str]]` | row serialization | `acceptable_map` | Explicit serialization to records. |
| `src/tools/geography_schemas.py` | `parent: Dict[str, str] \| None` | narrow map | `acceptable_map` | Value-map style parent geography. |
| `src/clients/chroma_utils.py` | `geo_for`, `geo_in` | `Dict[str, str]` | `acceptable_map` | Narrow filter maps. |

## Track 2 blockers that matter most

1. `src/state/types.py` still contains the main remaining contract failures: `messages`, `intent`, `geo`, `candidates`, `profile`, `history`, and `cache_index`.
2. `src/workflows/memory.py` and `src/services/memory_utils.py` still flatten and persist typed state through loose dict contracts.
3. The output path still has compatibility bridges: typed render data is adapted for legacy callers, `src/tools/chart_tool.py` / `src/tools/table_tool.py` still accept `str | dict` shims, LangChain `_run()` / `_arun()` paths still return string success messages, and render failures are logged rather than surfaced as typed failure artifacts.
4. `src/clients/census_api_utils.py` still exposes loose `geo` and `table_metadata` contracts, and the legacy `fetch_census_data()` wrapper is still alive under strict tooling.
5. `streamlit_app.py`, `src/api/displays.py`, and `src/clients/pdf_generator.py` now have typed/coercing display paths in key places, but their public/session wrappers remain compatibility adapters that can still receive raw dict payloads.
6. `src/domain/geography_registry.py`, `src/domain/geo_utils.py`, `src/domain/text_utils.py`, and `src/llm/intent_enhancer.py` still carry planning-relevant blobs.

## Track 2 closure rule

Track 2 should not be called complete while `blocking_any_dict` items still exist in the runtime planning, state, memory, agent, client, or UI result paths.
