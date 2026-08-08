# Agent-first grounded planning (target architecture)

**Status:** Target state — reconciles stated product intent with current implementation drift.  
**Authoritative for:** future graph refactors, ticket scoping, doc alignment.  
**Does not replace:** typed contracts, fail-closed validation, Chroma index invariants.

---

## Problem statement

The product goal is an **AI agent** that:

1. Reasons about the user's question in natural language
2. Queries the vector catalog (Chroma) for **semantic** similarity, filtered by dataset/year (default **2024** when no year is given, after temporal normalization)
3. Chooses **data category** (Detail B/C, Subject S, Profile DP, etc.), **table/group**, **variables**, and **geography level** from grounded retrieval evidence — see [`app_description/CENSUS_DISCUSSION.md`](../app_description/CENSUS_DISCUSSION.md)
4. **Composes and executes** Census Bureau API calls itself: builds `get=`, `for=`, `in=`, dataset path (`/{year}/acs/acs5`, subject, profile, …), and issues the request via tools — **not** receiving a pre-assembled URL from a upstream planner node
5. Runs a **multi-step tool loop** as reasoning requires (e.g. list CBSAs → pick code → build `in=` chain → resolve variables → fetch data → optional follow-up calls)
6. Analyzes returned data and answers — narrating assumptions and suggesting finer-grained follow-ups when the user did not specify a category

**Domain reference:** [`app_description/CENSUS_DISCUSSION.md`](../app_description/CENSUS_DISCUSSION.md) describes how categories, groups, variables, geography hierarchy, and example URLs relate. That doc is not exhaustive, but it defines the **decision space the agent must reason over** when constructing API parameters.

What shipped instead is a **planner-first** graph: regex search-text analysis, score-ranked auto-selection, and `geography_node` running **before** the agent and **halting** the graph with deterministic clarification. The agent is skipped when `requires_clarification=True`. When the agent does run, it often receives an **immutable** `GroundedCensusPlan` rather than owning parameter construction end-to-end.

That drift frustrates the core value proposition: the agent should **own reasoning**; deterministic code should **harness** (validate, trace, fail-closed), not **replace** retrieval and planning decisions.

---

## Principles (locked)

| Principle | Meaning |
|-----------|---------|
| **Agent reasons** | Interpret question, choose search queries, select among retrieved candidates, decide when to clarify vs proceed with a stated assumption |
| **Harness validates** | Pydantic contracts, candidate-ID grounding, strict Census API tool, retrieval traces — reject invented FIPS, table codes, or geo tokens |
| **Chroma is evidence, not authority** | Retrieval returns candidates + metadata; only **selected candidate IDs** attached to evidence become execution authority after validation |
| **Temporal year gates retrieval** | Resolved year (from `temporal_node`, default latest e.g. 2024) filters table/geo collections; agent uses that year in tool calls |
| **Clarification is agent dialogue** | When truly ambiguous among same-tier grounded options, agent asks — with readable labels and recommended default — not raw `table_0` dumps with agent skipped |
| **Breadth-first defaults** | Underspecified topic → agent picks the broad measure for that domain from catalog metadata, answers, then suggests granular breakdowns as follow-ups |
| **Deterministic math stays deterministic** | Comparison metrics, benchmark compute, temporal normalization — repeatable formulas remain code, not LLM |
| **Agent composes and executes API calls** | Agent decides `get`/`for`/`in`/dataset path and invokes Census tools; harness validates grounded tokens — does not build the call for the agent |
| **Multi-call tool loops** | Agent may call retrieval, geography enumeration, variable lookup, and Census fetch tools **multiple times** in one turn as reasoning requires |

---

## Agent-owned API construction (from CENSUS_DISCUSSION.md)

The agent — not a pre-agent workflow node — performs the analysis described in [`app_description/CENSUS_DISCUSSION.md`](../app_description/CENSUS_DISCUSSION.md):

| Decision | Agent reasoning (examples) | Grounding source |
|----------|---------------------------|------------------|
| **Dataset category** | Detail (B/C) vs Subject (S) vs Profile (DP) vs Comparison (CP) vs SPP | Chroma table collection + CENSUS_DISCUSSION § categories |
| **Year / dataset path** | `2023/acs/acs5`, `…/subject`, `…/profile` | Resolved temporal intent + table candidate metadata |
| **Table / group** | B01001, S1601, … | Chroma groups retrieval; variable URLs as follow-up |
| **Variables (`get=`)** | `NAME,B01001_001E` or `group(B01001)` | Variable catalog / group JSON; agent selects labels |
| **Geography level (`for=`)** | `county:*`, `metropolitan statistical area/micropolitan statistical area:*`, … | Chroma geo hierarchy + CENSUS_DISCUSSION § geography hierarchy table |
| **`in=` chains** | `county:*&in=state:06`; CBSA crosswalks | Agent may **first** call enumeration tools (`for=<level>:*`), cache codes, **then** build nested `in=` |

**Procedure (agent loop — paraphrased from CENSUS_DISCUSSION § "What to give your AI agent"):**

1. Pick dataset and year from question + temporal resolution.
2. If user needs a list of areas or ambiguous place names → call tools to enumerate `get=NAME,GEO_ID&for=<token>:*` (possibly filtered); use results to disambiguate.
3. When hierarchy is implied → construct `in=` chains from grounded codes (not invented FIPS).
4. Resolve table/group and variables via Chroma + optional groups/variables tools.
5. **Compose and execute** the final data URL via `StrictCensusApiTool` / `CensusAPITool`.
6. Analyze payload; optionally **additional tool calls** for comparisons, missing geographies, or finer breakdowns.

**Harness role:** Reject calls whose `for`/`in`/table codes are not traceable to retrieved evidence or validated enumeration results. **Not:** assemble the URL upstream and hand the agent a frozen plan only.

**Current gap:** `geography_node` + `GroundedCensusPlan` pre-select table and geo; agent tools execute within that box. Target: agent performs steps 1–6; validator confirms grounding before/after each Census fetch.

---

## Current vs target (honest gap)

### Current graph (`app.py`)

```
memory_load → temporal → geography → benchmark → comparison → agent → … → output
                              ↑
                    can halt here (TABLE_AMBIGUOUS, etc.)
                    agent skipped (agent.py: requires_clarification)
```

**Planner-first components (authority today — should become harness-only or agent tools):**

| Component | File | Role today | Target role |
|-----------|------|------------|-------------|
| `DeterministicCensusRetrievalAnalyzer` | `src/services/census_retrieval_analyzer.py` | Regex → search strings before agent | **Remove as planner authority**; optional hint helper for agent tools only |
| `geography_node` | `src/workflows/geography.py` | Sole planner: retrieve + score-select + clarify | **Validator/harness** or **post-agent plan check**; not graph halt |
| `select_grounded_plan` | `src/services/grounded_census_planner.py` | Score margin auto-select | **Validation helper only** — agent proposes IDs; planner verifies grounded |
| `geography_resume_node` | `src/workflows/geography.py` | Resume deterministic pending slots | **Agent turn** with checkpointed grounded options + conversation |
| Pre-agent clarify → `output` | `app.py` routing | User sees `table_0`… without agent | Agent-driven clarify or proceed-with-assumption |

**Already aligned with target:**

| Component | Role |
|-----------|------|
| `CensusQueryAgent` + tools | Agent execution loop (`TableSearchTool`, `GeographyDiscoveryTool`, `StrictCensusApiTool`, …) |
| `validate_grounded_plan` | Fail-closed on invented / incompatible IDs |
| `RetrievalEvidence`, `GroundedCensusPlan`, typed contracts | Trust boundaries |
| `temporal_node` | Year resolution before retrieval (keep early in graph) |
| Chroma collections + index builders | Semantic catalog (agent queries via tools) |
| `RetrievalTrace` + telemetry | Observability |

### Target graph (phased)

**Phase A — agent owns retrieval planning (minimal reorder)**

```
memory_load → temporal → agent_plan → validate_plan → agent_execute → comparison_metrics → output → memory_write
                ↑              ↑              ↑
           year filter    Chroma tools    fail-closed harness
                          + propose IDs
```

**Phase B — clarify without skipping agent**

- Pending clarification stores grounded options + trace; **next turn enters agent** with that context (not a separate non-agent resume path that bypasses reasoning).
- Agent may auto-select when one option is clearly best, or ask one focused question.

---

## Concrete shifts

### 1. Retrieval becomes an agent tool (not a pre-agent halt)

**Today:** `geography_node` calls `retrieve_table_candidates` / `retrieve_geography_candidates` internally.

**Target:**

- Agent invokes existing or consolidated tools (e.g. `TableSearchTool`, `GeographyDiscoveryTool`) with **agent-authored semantic queries** and `{year}` from resolved temporal intent.
- Tools return `RetrievalEvidence` (candidate IDs, scores, display names, metadata) — no auto-select.
- Agent iterates: refine query, inspect candidates, select IDs, or ask user.

**Implementation notes:**

- Wire `AgentPlanContext` / tool inputs with `resolved_year` from `WorkflowPlan.temporal`.
- Consolidate duplicate paths: workflow retriever vs agent tools should share `chroma_catalog_retriever.py`.
- Do **not** register score-rank selection inside tools; return evidence only.

### 2. `geography_node` → validator/harness (or post-agent)

**Today:** Only geography entry point; plans table + geo before agent.

**Target options (pick one in implementation ticket):

| Option | Description |
|--------|-------------|
| **A. Rename + shrink** | `validate_grounded_plan_node`: input = agent-proposed `GroundedSelection` + evidence; output = valid `GroundedCensusPlan` or structured errors back to agent |
| **B. Inline in agent loop** | Agent calls `GeographyValidationTool` / validator service after selecting IDs; graph node removed |
| **C. Lightweight gate** | Single node after agent planning turn that runs validator once before execution turn |

**Keep from current `geography_node`:**

- Evidence attachment, trace events, `GeographyIntent(source="chroma")` projection
- Fail-closed paths for stale index, schema mismatch, empty evidence

**Remove from authority:**

- `_LEADING_REQUEST` regex analyzer as first step
- `_ranked_id` / ambiguity margin as automatic decision
- Routing to `output` with agent skipped

### 3. Clarification = agent dialogue with grounded options

**Today:** `render_slot_clarification` + `PendingGeographyClarification` + `geography_resume_node`; agent skipped.

**Target:**

- Agent receives: `original_query`, `retrieval_evidence`, `pending_options` (IDs + labels + metadata), `requested_slot`.
- Agent outputs either:
  - **Proceed:** `{table_id, hierarchy_id, area_ids[]}` grounded in evidence, with short assumption text, or
  - **Clarify:** natural-language question + ranked recommendations (not raw enum dump)
- Checkpoint stores conversation + evidence snapshot (existing SQLite checkpointer).
- **Breadth-first:** if user gave geography but not topic, agent defaults to broad table and states what finer tables exist.

### 4. Deterministic layer: keep vs lose

| Keep (harness) | Lose (planner authority) |
|----------------|-------------------------|
| Pydantic typed contracts | Regex `DeterministicCensusRetrievalAnalyzer` as graph entry |
| `validate_grounded_plan` / strict API tool | `select_grounded_plan` score-rank auto-select |
| Candidate-ID-only execution | Pre-agent `requires_clarification` agent skip |
| `RetrievalTrace`, telemetry | `table_0`…`table_11` user-facing clarify without agent |
| Temporal/benchmark/comparison **math** | Code allowlists (e.g. B01001 preference) |
| Fail-closed on hallucinated geo/table codes | Implicit US default, pickle caches, legacy mappings |

---

## Agent tool surface (target)

Existing tools in `src/agents/census_query_agent.py` are the seed. Target responsibilities:

| Tool / service | Agent use |
|----------------|-----------|
| `TableSearchTool` | Semantic table retrieval for `{query, year}` → evidence list |
| `GeographyDiscoveryTool` / hierarchy / area tools | Geo retrieval constrained by selected dataset+year |
| `GeographyValidationTool` | Check proposed tokens against evidence |
| `StrictCensusApiTool` | Execute only validated `GroundedCensusPlan` |
| `VariableValidationTool` | Column/variable grounding |
| Validator service (non-tool) | Graph harness: reject plan before API if IDs not in evidence |

New or extended tools as needed:

- **`CatalogRetrievalTool`** — unified Chroma query returning typed `RetrievalEvidence` for any collection
- **`ProposeGroundedPlanTool`** — agent submits candidate ID selection for harness validation

---

## Migration phases (suggested tickets)

| Phase | Scope | Success signal |
|-------|--------|----------------|
| **0. Doc alignment** | Reconcile all architecture docs to this file; mark planner-first sections as legacy | No doc claims agent is "execution owner" while graph skips agent on clarify |
| **1. Agent planning turn** | After `temporal`, run agent with retrieval tools only; no API until plan validated | CLI question reaches agent on turn 1; no `agent: skipped` on table ambiguity |
| **2. Validator harness** | Replace `geography_node` authority with `validate_grounded_plan` gate | Invented IDs still fail; agent can recover |
| **3. Agent clarification** | Merge `geography_resume` into agent checkpoint flow | Two-turn table/geo flows are conversational |
| **4. Retire planner select** | Demote `select_grounded_plan` to test helper / proposed-ID checker | No score-rank in production path |
| **5. Index metadata** | Table `category`, universe, breadth in Chroma metadata for agent defaults | Broad population ≠ housing false positives |

**CENSUS-21 (merged/in PR):** table-slot **resume plumbing** inside planner-first graph — **keep** as interim seam; **do not** treat as final architecture.

---

## Acceptance criteria (architecture — not single question)

1. **Turn 1 agent participation:** Natural-language Census question always reaches the reasoning node; no silent skip for `requires_clarification`.
2. **Semantic retrieval:** Table/geo candidates come from agent-tool Chroma queries using resolved year, not regex-only search text as sole input.
3. **Grounded execution:** Every API call traceable to candidate IDs in attached evidence; validator rejects inventions.
4. **Useful clarification:** When agent clarifies, user sees reasoning + recommended default + follow-up paths — not only `table_N` labels.
5. **Repeatable harness:** Same agent nondeterminism is allowed for wording; **validated plan + API URLs** remain stable for same grounded ID choices.
6. **Golden corpus:** Tier 1 URL/geo contracts still pass via replay; Tier 3 NL may require agent-default policy documented separately.

---

## Document map (legacy vs target)

| Document | Current stance | Action |
|----------|----------------|--------|
| `app_description/ARCHITECTURE.md` | Says agent execution owner; describes planner-first `geography_node` | **Rewrite** graph + geography sections to match this doc |
| `docs/chroma_geography_architecture.md` | `geography_node` sole entry; no LLM resolver | **Rewrite** runtime authority section |
| `docs/census-21-reframe.md` | Planner-first table resume | **Add banner** — interim fix, not target |
| `docs/track-2_framework.md` | Mixed: scaffolding principle vs deterministic planning steps | **Clarify** deterministic = contracts + math, not retrieval |
| `docs/typed_contracts.md` | Deterministic planning layer | **Reframe** as typed harness, not planner replacement |
| `docs/chroma_geography_operator_runbook.md` | Ops/index focus | Minor: note agent queries same collections |
| `README.md`, `USAGE_GUIDE.md` | May imply automatic answers | **User-facing** agent-first flow |

See **`docs/prompts/doc-alignment-agentic-shift.md`** for the full doc-alignment agent prompt.  
**Completed (2026-08-08):** **`docs/DOC_ALIGNMENT_CHANGELOG.md`** — inventory, glossary, file list, remaining implementation tickets.

---

## References (code)

- Graph: `app.py`, `src/workflows/geography.py`, `src/workflows/agent.py`
- Analyzer (legacy authority): `src/services/census_retrieval_analyzer.py`
- Planner select (legacy authority): `src/services/grounded_census_planner.py`
- Validator (keep): `src/services/grounded_plan_validator.py`
- Agent tools: `src/agents/census_query_agent.py`, `src/tools/`
- Stated intent (already correct): `app_description/ARCHITECTURE.md` L12, `docs/track-2_framework.md` L5–8
