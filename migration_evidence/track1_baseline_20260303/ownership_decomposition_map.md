# Track 1 Step 2 - Ownership Decomposition Map

## Scope
- Goal: Decompose `src/utils/` into explicit ownership by layer.
- Rule: Structural classification only (no behavior changes in this step).
- Layer order: `domain -> clients -> services -> agents -> workflows -> api`

## Status Legend
- `P1`: low-risk, move early in Step 3
- `P2`: medium-risk, move after P1
- `P3`: high-risk, move last in Track 1

## Target Layer Definitions

| Target layer | Explanation |
|---|---|
| `domain` | Pure business rules, canonical models, and deterministic transformations with no external I/O dependencies. |
| `clients` | Adapters/wrappers for external systems (APIs, files, vector stores, telemetry, rendering engines). |
| `services` | Orchestration logic that composes domain rules and client calls into application use-cases. |
| `agents` | LLM/agent reasoning implementation and response shaping that coordinates tools/contracts. |
| `workflows` | Node/graph sequencing and state transition wiring across execution steps. |
| `api` | User-facing transport/presentation adapters (CLI, Streamlit, HTTP) that expose internal services/workflows. |

## Ownership Map

| Current file | Current responsibility | Target layer | Why this layer | Depends on (high-level) | Used by (high-level) | Move priority | Risk notes |
|---|---|---|---|---|---|---|---|
| `src/utils/geography_registry.py` | Geography token normalization, lookup, area enumeration | `domain` | Core geography logic and rules | geography metadata, stdlib | tools/services | P1 | Large surface area; validate imports after move |
| `src/utils/geo_utils.py` | Geography filter parsing and hint resolution helpers | `domain` | Pure geo transformation logic | stdlib | nodes/services | P1 | Ensure no hidden I/O coupling |
| `src/utils/text_utils.py` | Query text parsing helpers (years, tokens) | `domain` | Pure text rules with no transport concern | stdlib/regex | services/llm helpers | P1 | Low risk |
| `src/utils/census_groups.py` | Census table/group constants and mappings | `domain` | Canonical metadata/constants | none/stdlib | tools/services | P1 | Low risk |
| `src/utils/time_utils.py` | Time/date utility helpers | `domain` | Pure utility logic | stdlib | multiple layers | P1 | Low risk |
| `src/utils/census_api_utils.py` | Build/normalize Census API query params and URL pieces | `clients` | External API request-shape concerns | census endpoint conventions | tools/services | P1 | Verify no business logic leaks in helpers |
| `src/utils/chroma_utils.py` | Chroma/embedding data handling and geo metadata support | `clients` | External data-store integration concern | chroma client, metadata schema | tools/services | P2 | Potential coupling with service logic |
| `src/utils/file_utils.py` | File persistence helpers for generated artifacts | `clients` | I/O boundary abstraction | filesystem | tools/output workflow | P2 | Confirm all paths remain stable |
| `src/utils/session_logger.py` | Session and run log persistence | `clients` | Logging sink / external write concern | filesystem/logging | app entrypoints/workflows | P2 | Path and naming assumptions |
| `src/utils/telemetry.py` | Event telemetry recording | `clients` | External observability boundary | logging/telemetry backend | nodes/services | P2 | Keep payload schema unchanged |
| `src/utils/pdf_generator.py` | PDF rendering/export integration | `clients` | Output format I/O adapter | PDF library, filesystem | output path/tools | P2 | Formatting regressions if moved incorrectly |
| `src/utils/dataframe_utils.py` | DataFrame shaping/format helpers | `services` | Business-level data shaping support | pandas-like data ops | tools/output/services | P2 | Confirm chart/table expectations unchanged |
| `src/utils/dataset_geography_validator.py` | Validate geography support per dataset/year | `services` | Business validation orchestration | registry + dataset rules | tools/agent path | P2 | Behavior-sensitive validation messages |
| `src/utils/variable_validator.py` | Variable-level validation and alternatives | `services` | Business validation logic | census metadata + helpers | tools/agent path | P2 | Output contract relied on by tests |
| `src/utils/enumeration_detector.py` | Detect/construct enumeration requests from query intent | `services` | Orchestration support between intent and geo execution | regex + geo metadata | planning/agent path | P2 | Query interpretation is behavior-sensitive |
| `src/utils/footnote_generator.py` | Compose citations/disclaimers from result context | `services` | Domain-facing output composition logic | templates/rules | `nodes/agent.py` | P2 | Keep footnote count/format stable |
| `src/utils/displays.py` | CLI display formatting/rendering | `api` | Presentation adapter for CLI surface | stdout/render formatting | `main.py` output | P2 | User-visible text changes are regressions |
| `src/utils/conversation_summarizer.py` | Summarize long agent intermediate steps | `services` | Workflow support logic without transport ownership | llm callback utils | `census_query_agent.py` | P3 | May affect agent behavior if touched |
| `src/utils/memory_utils.py` | Build/update memory profile/history structures | `services` | Stateful business logic | state schema/history rules | `nodes/memory.py` | P3 | High coupling with memory node and tests |
| `src/utils/agents/census_query_agent.py` | ReAct agent orchestration and output parsing | `agents` | Agent implementation ownership | langchain + tools + llm | `nodes/agent.py`, tests | P3 | High risk; duplicate methods/sys.path cleanup required in Track 1 |
| `src/utils/__init__.py` | Package marker | (remove/repurpose) | Legacy `utils` package shell | none | imports | P3 | Final cleanup after moves complete |

## Cross-check Mapping (Step 2 planning only)

| Current area | Planned target area |
|---|---|
| `src/tools/*.py` | service adapters around domain/clients/service contracts (remain tool-facing in Track 1) |
| `src/nodes/agent.py`, `src/nodes/memory.py`, `src/nodes/output.py` | `workflows/` in Step 3 |
| CLI/Streamlit entry rendering | `api/` adapters in Step 3+ |

## Proposed Step 3 Move Order (Dependency-first)
1. `domain` P1 files (`geography_registry`, `geo_utils`, `text_utils`, `census_groups`, `time_utils`)
2. `clients` P1/P2 files (`census_api_utils`, then chroma/file/session/telemetry/pdf)
3. `services` P2 files (`dataset_geography_validator`, `variable_validator`, `enumeration_detector`, etc.)
4. `agents` P3 (`census_query_agent.py`)
5. `workflows` (`src/nodes/*`) and final `api` path cleanup

## Step 2 Completion Criteria
- Every `src/utils/*.py` module has one target owner layer.
- No module remains in "unknown ownership".
- P1/P2/P3 priorities are assigned for Step 3 sequencing.
- High-risk modules are explicitly flagged before any move.
