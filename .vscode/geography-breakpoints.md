# Geography debugger breakpoint map

Use `Geography: Golden row 3` for the canonical county-in-state failure or
`Geography: Choose golden row` for another fixture. VS Code stores source
breakpoints in user workspace state, so they cannot be committed in
`launch.json`; add the breakpoints below by symbol.

## Core path

| Stage | File and symbol | Inspect |
| --- | --- | --- |
| Graph input | `src/workflows/geography.py:geography_node` | `user_question`, `existing`, `state.profile` |
| Routing | `app.py:_route_after_geography` | `state.plan.requires_clarification` |
| Retrieval analysis | `src/services/census_retrieval_analyzer.py:analyze_retrieval_request` | search phrases only; no canonical codes |
| Table retrieval | `src/services/chroma_catalog_retriever.py:retrieve_table_candidates` | query, metadata filters, IDs, distances |
| Geography retrieval | `src/services/chroma_catalog_retriever.py:retrieve_geography_candidates` | dataset/year filters, levels, areas, hierarchy |
| Selection | `src/services/grounded_census_planner.py:select_grounded_plan` | supplied IDs versus selected IDs |
| Validation | `src/services/grounded_plan_validator.py:validate_grounded_plan` | unknown IDs, parent ordering, compatibility |
| Agent boundary | `src/workflows/agent.py:agent_reasoning_node` | immutable plan context and skip reason |
| Model call | `src/agents/runtime/modern_backend.py:ModernBackend.invoke` | messages and tool calls |
| Tool trace | `src/agents/adapters/message_to_executor.py:message_trace_to_executor_result` | tool name, arguments, observation |
| API guard | `src/tools/strict_census_api_tool.py:StrictCensusApiTool._run` | grounded evidence and request |
| Geography encoding | `src/clients/census_api_utils.py:build_geo_filters` | canonical `for` and ordered `in` |
| URL construction | `src/clients/census_api_utils.py:build_census_url` | final URL without logging the API key |

## Conditional breakpoints

Add these conditions at the indicated branch:

- Chroma query result handling: `result.status in {"empty", "unavailable", "stale", "schema_mismatch"}`
- Candidate score threshold: `top_score < minimum_score`
- Ambiguity branch: `len(candidates) > 1 and top_score - second_score < ambiguity_margin`
- Selection validation: `any(item not in candidate_ids for item in selected_ids)`
- Hierarchy validation: `required_parents != provided_parents`
- Geography routing: `state.plan is not None and state.plan.requires_clarification`
- Strict API response: `response.success is False`
- Agent loop: `"iteration limit" in str(execution.output).lower()`

## Logpoints

Use logpoints when a stop would disturb an LLM/tool loop:

- Retrieval: `trace={trace_id} collection={collection_name} filters={where} candidates={candidate_ids}`
- Ranking: `trace={trace_id} top={top_score} second={second_score} margin={ambiguity_margin}`
- Selection: `trace={trace_id} selected={selected_ids}`
- Validation: `trace={trace_id} status={status} reason={reason_code}`
- API guard: `trace={trace_id} evidence={evidence_ids} allowed={allowed}`
- URL: `trace={trace_id} dataset={dataset} year={year} for={geo_for} in={geo_in}`

Never log `OPENAI_API_KEY`, `CENSUS_API_KEY`, full environment dictionaries, or
URLs after an API key has been appended.

## Failure scenarios

1. Row 3: county wildcard plus California parent must select `county:*` and
   `state:06`, not two competing geographies.
2. Row 20: block group must retain state, county and tract parent order.
3. Row 98: tribal `(or part)` tokens must remain canonical and untruncated.
4. `Population of Springfield`: retrieval must expose official alternatives
   and route to clarification.
5. Empty or unavailable geography collection: the pipeline must return a
   `GEOGRAPHY_PARTITION_MISSING` or `GEOGRAPHY_INDEX_UNAVAILABLE`
   clarification, never `us:1`.
6. Fabricated selector ID: validation must reject it before any Census API
   tool executes.
