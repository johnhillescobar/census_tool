# Census Tool Architecture

**Last updated**: July 17, 2026  
**Status**: Current implementation reference (Track 2 deterministic planning + agent-first execution)  
**Purpose**: Single source of truth for how the Census Tool is wired today

---

## 1. Executive Summary

The Census Tool is a local Census Q&A application built on **LangGraph**, **ChromaDB**, and the **US Census API**. It combines:

1. **Deterministic planning nodes** (temporal, benchmark, comparison) that normalize ambiguous user input into typed contracts and fail closed to clarification when needed.
2. **A reasoning agent** (`CensusQueryAgent`) that remains the **execution owner** for Census data retrieval, using ReAct-style tool loops.
3. **Deterministic post-processing** (comparison metrics, chart/table rendering, presentation routing) that turns agent artifacts into UI-ready outputs.

### Canonical principle

Deterministic contracts and workflow/service steps are **reliability scaffolding** that empower AI reasoning nodes. They must **not** replace the reasoning node.

- Planning nodes clarify and gate ambiguous input early.
- The agent performs repeated typed Census tool calls and drives answer/chart/table directives.
- Downstream nodes compute comparison metrics and render artifacts without re-interpreting free text.

---

## 2. Workflow Graph

**Entry point**: `app.py` → `create_census_graph()`

The graph is **not** a simple 4-node linear flow. It has **8 nodes** with conditional routing for clarification and benchmark bypass.

```
memory_load
    → temporal ──(clarification?)──→ output
    → benchmark ──(clarification?)──→ output
                ──(benchmark N/A?)──→ agent
                ──(else)──────────→ comparison
    → comparison ──(clarification?)──→ output
                 ──(else)──────────→ agent
    → agent ──(clarification?)──→ output
            ──(else)──────────→ comparison_metrics
    → comparison_metrics → output → memory_write → END
```

### Node responsibilities

| Node | Module | Role |
|------|--------|------|
| `memory_load` | `src/workflows/memory.py` | Load user profile, history, cache index from SQLite checkpoints |
| `temporal` | `src/workflows/temporal.py` | Resolve `TemporalIntent` via `temporal_policy`; may set `requires_clarification` |
| `benchmark` | `src/workflows/benchmark.py` | Resolve `BenchmarkIntent` or mark benchmark not applicable |
| `comparison` | `src/workflows/comparison.py` | Build `ComparisonPlan` from resolved temporal + benchmark |
| `agent` | `src/workflows/agent.py` | Call `CensusQueryAgent.solve()` with optional `AgentPlanContext` |
| `comparison_metrics` | `src/workflows/comparison_metrics.py` | Deterministic metric compute from `comparison_input_rows` |
| `output` | `src/workflows/output.py` | Render charts/tables; populate `generated_files` via typed artifacts |
| `memory_write` | `src/workflows/memory.py` | Persist conversation state |

Routing helpers live in `app.py`: `_route_after_temporal`, `_route_after_benchmark`, `_route_after_comparison`, `_route_after_agent`.

Typed node return values should use `CensusGraphPatch` (`src/workflows/graph_patch.py`) at the LangGraph boundary.

---

## 3. Typed Contracts (`src/domain/`)

Track 2 planning artifacts are Pydantic models with strict validation (`extra="forbid"`).

### Planning contracts

| Model | File | Purpose |
|-------|------|---------|
| `TemporalIntent` | `temporal_contract.py` | Normalized time scope (`point_in_time`, `range`, `latest_available`, etc.) |
| `BenchmarkIntent` | `benchmark_contract.py` | Comparison target, operator, normalization, geography level |
| `ComparisonPlan` | `comparison_plan.py` | Query years, dataset, metric, derived metrics, join keys |
| `WorkflowPlan` | `src/state/workflow_plan.py` | Aggregates temporal/benchmark/comparison resolution + `requires_clarification` |

Resolution wrappers (`TemporalResolved`, `BenchmarkResolved`, `BenchmarkNotApplicable`, clarification variants) discriminate on a `status` field.

### Agent and data contracts

| Model | File | Purpose |
|-------|------|---------|
| `AgentPlanOutput` | `agent_output_contract.py` | Validated agent JSON output (`census_data`, `answer_text`, `charts_needed`, …) |
| `AgentPlanContext` | `agent_plan_context.py` | Plan directives injected into agent prompt |
| `StrictCensusApiResponse` | `census_tool_contract.py` | Typed strict Census API tool response |
| `ComparisonInputRow` | `comparison_artifacts.py` | Rows for deterministic metric compute |
| `ComparisonMetricArtifactRow` | `comparison_artifacts.py` | Computed comparison metrics |

### Output and presentation contracts

| Model | File | Purpose |
|-------|------|---------|
| `RenderedArtifactSuccess` / `RenderedArtifactFailure` | `rendered_output_contract.py` | Typed chart/table export results in `final.generated_files` |
| `PresentationRouting` | `presentation_contract.py` | Deterministic UI routing (`SINGLE_VALUE`, `TIME_SERIES`, `CLARIFICATION`, …) |

Presentation routing is computed in `src/services/presentation_routing.py` from state — not from agent prose.

See also: `docs/typed_contracts.md` (layman's guide to typed contracts).

---

## 4. Services Layer (`src/services/`)

Deterministic policy and computation live here (not in workflow nodes):

| Service | Role |
|---------|------|
| `temporal_policy.py` | Text → `TemporalResolution` |
| `benchmark_policy.py` | Text → `BenchmarkResolution` |
| `benchmark_geo_inference.py` | Geography hints for benchmark targets |
| `comparison_plan_policy.py` | Temporal + benchmark → `ComparisonPlan` |
| `comparison_input_builder.py` | Agent census data → `ComparisonInputRow` list |
| `comparison_metric_compute.py` | Rows + plan → derived metrics |
| `agent_plan_context.py` | `WorkflowPlan` → agent prompt directives |
| `presentation_routing.py` | `CensusState` → `PresentationRouting` |
| `workflow_acceptance_runner.py` | Canonical acceptance plan runner |

Supporting services: `memory_utils`, `variable_validator`, `dataset_geography_validator`, `enumeration_detector`, `footnote_generator`, `conversation_summarizer`, `dataframe_utils`.

---

## 5. Agent Design (`CensusQueryAgent`)

**Location**: `src/agents/census_query_agent.py`

Uses LangChain `create_react_agent` + `AgentExecutor` with structured output validation via `AgentPlanOutput`.

### Registered tools (11)

| Tool | Module | Notes |
|------|--------|-------|
| `GeographyDiscoveryTool` | `geography_discovery_tool.py` | Enumerate geography levels/areas |
| `GeographyValidationTool` | `geography_validation_tool.py` | Validate geography against dataset rules |
| `TableSearchTool` | `table_search_tool.py` | ChromaDB semantic table search |
| `CensusAPITool` | `census_api_tool.py` | Legacy Census API execution |
| `StrictCensusApiTool` | `strict_census_api_tool.py` | Typed strict Census API calls |
| `TableTool` | `table_tool.py` | CSV/Excel/HTML export |
| `PatternBuilderTool` | `pattern_builder_tool.py` | Census API URL patterns |
| `AreaResolutionTool` | `area_resolution_tool.py` | Name → FIPS resolution |
| `ChartTool` | `chart_tool.py` | Plotly chart generation |
| `GeographyHierarchyTool` | `geography_hierarchy_tool.py` | Geography hierarchy navigation |
| `VariableValidationTool` | `variable_validation_tool.py` | Variable/table validation |

**Not registered** (exists but unused by agent): `TableValidationTool` (`table_validation_tool.py`).

The agent accepts optional `AgentPlanContext` from the workflow plan so comparison/temporal directives are injected deterministically.

Offline mode: if `OPENAI_API_KEY` is missing and `allow_offline=True`, the agent initializes without tools (parsing helpers only).

---

## 6. State Management

**Schema**: `src/state/types.py` — `CensusState` (Pydantic `BaseModel` with LangGraph `Annotated` reducers)

Key channels:

- `messages` — append
- `plan` — overwrite (`WorkflowPlan | None`)
- `artifacts` — merge dict (includes `census_data`, `comparison_input_rows`, `comparison_metrics`, …)
- `final` — overwrite (answer text, chart/table specs, `generated_files`)
- `profile`, `cache_index` — merge dict
- `logs` — append

Typed views: `FinalResponseState`, `WorkflowArtifactsState` (projected via helper functions for LangGraph compatibility).

Checkpoints: SQLite (`checkpoints.db`) via `SqliteSaver`, with in-memory fallback.

---

## 7. Clients and Presentation

| Module | Role |
|--------|------|
| `src/clients/census_api_utils.py` | Census API HTTP client |
| `src/clients/chroma_utils.py` | ChromaDB table index access |
| `src/clients/file_utils.py` | Cache read/write, retention |
| `src/clients/pdf_generator.py` | Streamlit session PDF export |
| `src/clients/session_logger.py` | CLI session logging |
| `src/clients/telemetry.py` | Telemetry hooks |
| `src/api/displays.py` | CLI result formatting |

Entry points: `main.py` (CLI), `streamlit_app.py` (web), `launcher.py` (chooser).

---

## 8. Testing

**Location**: `app_test_scripts/`  
**Collected**: 281 tests (`uv run pytest app_test_scripts/ --collect-only -q`)

Track 2 coverage includes:

- Contract tests: `test_temporal_policy_contract.py`, `test_benchmark_contract.py`, `test_comparison_*`
- Graph wiring: `test_track2_graph_invoke.py`, `test_benchmark_workflow_routing.py`, `test_graph_patch_contract.py`
- Agent integration: `test_agent_reasoning_node.py`, `test_agent_plan_context.py`, `test_rendered_output_contract.py`
- Acceptance: `test_workflow_acceptance_plans.py`

Some tests require live LLM/API keys (`test_census_query_agent.py`, `test_integration_agent_api.py`, `test_e2e_workflows.py`).

```bash
# Full suite
uv run pytest app_test_scripts/ -v

# Fast unit/contract subset (excludes live LLM integration)
uv run pytest app_test_scripts/ -q \
  --ignore=app_test_scripts/test_integration_agent_api.py \
  --ignore=app_test_scripts/test_census_query_agent.py \
  --ignore=app_test_scripts/test_e2e_workflows.py
```

---

## 9. Project Structure (active paths)

```
census_tool/
├── app.py                          # LangGraph definition (8 nodes)
├── main.py, streamlit_app.py, launcher.py
├── config.py
├── src/
│   ├── domain/                     # Typed contracts
│   ├── services/                   # Deterministic policy + compute
│   ├── workflows/                  # Graph nodes + graph_patch
│   ├── agents/census_query_agent.py
│   ├── tools/                      # Agent tools
│   ├── state/types.py, workflow_plan.py
│   ├── clients/                    # External I/O
│   ├── api/displays.py
│   └── llm/                        # Factory, config, prompts
├── app_test_scripts/
├── docs/                           # track-2_framework.md, typed_contracts.md
├── app_description/                # This file + output format specs
├── index/                          # ChromaDB index builder
├── data/, memory/, chroma/         # Runtime artifacts
└── migration_evidence/             # Track baselines and gap registers
```

---

## 10. Related Documentation

| Document | Audience |
|----------|----------|
| `README.md` | User-facing overview and setup |
| `ARCHITECTURE_GUIDE.md` | Onboarding guide for contributors |
| `USAGE_GUIDE.md` | CLI vs Streamlit usage |
| `docs/track-2_framework.md` | Track 2 scope, policy decisions, acceptance criteria |
| `docs/typed_contracts.md` | Plain-language explanation of typed contracts |
| `app_description/output_format_docs/AGENT_OUTPUT_FORMAT.md` | Agent JSON output spec |

---

## 11. Maintenance Notes

### Adding a tool

1. Create `src/tools/my_tool.py` (`BaseTool` subclass).
2. Register in `CensusQueryAgent.__init__()` tools list.
3. Update agent prompt in `src/llm/config.py` if behavior changes.
4. Add tests under `app_test_scripts/`.

### Changing the graph

1. Edit `app.py` nodes/edges/routing.
2. Update affected workflow modules and `CensusGraphPatch` usage.
3. Run `test_track2_graph_invoke.py` and routing tests.
4. Regenerate `graph.png` (automatic on graph compile when visualization succeeds).
5. Update this document and `README.md`.

### Changing contracts

1. Update Pydantic models in `src/domain/`.
2. Update services that produce/consume them.
3. Update contract tests and acceptance plans.
4. Keep `WorkflowPlan` as the single planning aggregate on `CensusState.plan`.

---

**This document describes the running architecture as of July 2026. For migration history and baseline evidence, see `migration_evidence/`.**
