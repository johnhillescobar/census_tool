# Prompt: Align repository documentation to agent-first grounded planning

**Use this prompt with a fresh agent session.** Goal: audit and rewrite project documentation so it consistently describes **agent-first reasoning with deterministic harnesses** — not planner-first deterministic search that blocks the agent.

**Target architecture (source of truth):** [`docs/agent-first-grounded-planning.md`](../agent-first-grounded-planning.md)

**Do not** implement code changes in this pass unless explicitly asked. This is a **documentation alignment** task.

---

## Copy-paste prompt (start here)

```
You are aligning the census_tool repository documentation to an agent-first architecture.

Read first:
- docs/agent-first-grounded-planning.md (TARGET — treat as authoritative)
- app_description/CENSUS_DISCUSSION.md (DOMAIN — how Census API params are built: categories, groups, variables, for/in, multi-step enumeration)
- app.py graph wiring
- src/workflows/agent.py (note: agent skipped when requires_clarification)
- src/workflows/geography.py (note: pre-agent planner that can halt graph)
- src/agents/census_query_agent.py (existing agent tools)

## Product intent (non-negotiable)

The user builds an AI Census assistant where:

### Reasoning and retrieval
1. The **AGENT** reasons about the natural-language question (topic, geography scope, comparison intent, time).
2. The **AGENT** (via tools) queries Chroma vector collections for semantic similarity, filtered by dataset/year (defaults to **`LATEST_AVAILABLE_YEAR`** in `config.py` when no year is stated, after `temporal_node`).
3. The **AGENT** chooses **data category** (Detail B/C, Subject S, Profile DP, etc.), table/group, variables, and **geography level** from **grounded** retrieval evidence — using the decision space documented in `app_description/CENSUS_DISCUSSION.md` (categories, hierarchy, `for`/`in` patterns, crosswalk queries). That doc is not fully exhaustive but defines the API-construction model.

### API call ownership (critical — do not soft-pedal)
4. The **AGENT composes Census Bureau API parameters** — dataset path (`/{year}/acs/acs5`, subject, profile, …), `get=` variables, `for=` geography level, `in=` parent chains — based on its reasoning about category, geography, and table. This is **agent analysis**, not a pre-agent planner emitting a frozen URL.
5. The **AGENT executes** those API calls via tools (`StrictCensusApiTool`, `CensusAPITool`, geography enumeration tools, etc.). Execution is part of the agent loop, not a separate batch job after a non-agent node finishes.
6. The **AGENT may call tools multiple times** in one session as reasoning requires — e.g. enumerate CBSAs → pick code → build `in=` chain → resolve variables → fetch → compare counties with a second fetch. Multi-step loops are a feature, not a failure mode.

### Answer and follow-ups
7. The **AGENT** analyzes returned data and answers the question — stating assumptions (e.g. broad Detail table when category unspecified) and suggesting finer-grained follow-ups (race, age, subject tables, etc.).

### Harness (not replacement)

In this project, **deterministic code is a harness only** — reliability scaffolding that constrains the agent at trust boundaries. It validates, traces, and fail-closes; it does **not** reason, retrieve, compose API parameters, or decide multi-call strategy. Typed contracts and the strict Census API tool are the **rails**; the agent is the **driver**.

**KEEP (harness):**
- Pydantic typed contracts (`TemporalIntent`, `GeographyIntent`, `GroundedCensusPlan`, …)
- `validate_grounded_plan` — reject invented FIPS, table codes, or geo tokens not in evidence
- Strict Census API tool — execution guard aligned to grounded evidence
- Fail-closed on hallucinated or ungrounded codes (no silent fallbacks)
- `RetrievalTrace` / telemetry — observability receipt for each stage
- Deterministic comparison / benchmark **math** (repeatable formulas, not LLM)

**LOSE as authority** (these are legacy planner-first drift, not harness):
- Regex `DeterministicCensusRetrievalAnalyzer` as graph entry (replacing agent retrieval reasoning)
- `select_grounded_plan` score-rank auto-select (replacing agent table/geo choice)
- `geography_node` halting the graph before the agent runs
- `requires_clarification` skipping the agent (`agent: skipped`)
- Raw `table_0` / `table_1` clarification dumps without agent narration
- Code allowlists (e.g. B01001 preference) as policy
- Upstream assembly of immutable API plans that prevent agent parameter reasoning

**What "LOSE as authority" means (deprecation lifecycle — not "delete code in this pass"):**
1. **Document as Legacy / migration debt** — stop describing these as the primary runtime path.
2. **Do not extend** — no new features, allowlists, or tickets that deepen planner-first behavior.
3. **Refactor or reroute** — demote to harness-only (e.g. validator) or remove from graph path in implementation phases (see `agent-first-grounded-planning.md`).
4. **Delete later** — only after agent-first path replaces the behavior and tests pass. This doc-alignment pass is markdown only unless explicitly asked otherwise.

The repo ALREADY STATES harness intent in places (app_description/ARCHITECTURE.md L12, docs/track-2_framework.md L5-8) but IMPLEMENTATION DOCS contradict it by describing geography_node as sole planner and deterministic search as authority.

## Your task

### Phase 1 — Inventory (output a table)

Search all *.md in the repo (docs/, app_description/, README.md, USAGE_GUIDE.md, ARCHITECTURE_GUIDE.md, migration_evidence/, .cursor/rules/, .vscode/, .github/). For each file, classify:

| Column | Values |
|--------|--------|
| Path | file path |
| Stance | agent-first / planner-first / mixed / ops-only / historical |
| Conflict | one sentence: what contradicts target architecture |
| Action | rewrite / add banner / deprecate section / no change |
| Priority | P0 (architecture lies) / P1 (misleading) / P2 (minor) |

Flag P0 files that tell readers the agent is "execution owner" while describing a graph where geography_node blocks before agent.

Known P0 candidates (verify and extend):
- app_description/ARCHITECTURE.md
- app_description/CENSUS_DISCUSSION.md (ensure aligned with agent-first — may need "target runtime" section, not just API reference)
- docs/chroma_geography_architecture.md
- docs/census-21-reframe.md
- docs/track-2_framework.md (step 4 "deterministic planning flow")
- docs/typed_contracts.md (deterministic planning layer framing)
- migration_evidence/golden_urls/fix_pr_backlog_plan.md
- README.md / USAGE_GUIDE.md if they promise automatic answers

### Phase 2 — Terminology glossary (output)

Produce a short glossary to use consistently across docs:

| Term | Definition |
|------|------------|
| Agent-first | Agent reasons, retrieves, **composes API params**, **executes** Census tools (possibly many times), analyzes, narrates |
| Harness | Reliability scaffolding at trust boundaries: validators, typed contracts, traces, fail-closed guards, deterministic comparison math — **constrain** the agent, **do not replace** reasoning, retrieval, API composition, or multi-call loops |
| Lose as authority | Stop using as runtime decision-maker; mark **Legacy / migration debt** in docs; do not extend; refactor to harness or remove from graph in implementation phases — **not** immediate code deletion in this doc pass |
| Grounded | Candidate IDs / enumerated geo codes from Chroma or Census list tools — agent may not invent FIPS or table codes |
| API composition | Agent builds `get`/`for`/`in`/dataset path per CENSUS_DISCUSSION.md; not planner-emitted frozen URL |
| Multi-call loop | Agent iterates tools until it has enough evidence to answer (enumerate → disambiguate → fetch → optional refetch) |
| Planner-first (LEGACY) | geography_node + analyzer + score-select before agent — mark as migration debt |
| Clarification | Agent-driven dialogue with grounded options, not deterministic halt |

Ban or qualify these phrases in architecture docs:
- "deterministic planning layer" → unless scoped to contracts + math only
- "geography_node is the only entry point" → legacy; target is agent tools + validator
- "no LLM geography resolver" → rephrase: no ungrounded LLM geo codes; agent may resolve among grounded candidates
- "same input → same plan" → qualify: same grounded ID choices → same validated plan; agent wording may vary

### Phase 3 — Rewrites (execute for P0 files)

For each P0 file, produce concrete edits:

1. **app_description/ARCHITECTURE.md**
   - Update graph diagram: temporal → agent planning (retrieval tools) → validate → agent execute
   - Move current geography_node sequence to "Legacy planner path (migration debt)" or rewrite as validator harness
   - Clarify agent tool ownership of Chroma search

2. **docs/chroma_geography_architecture.md**
   - Replace "geography_node is the only geography planning entry point" with agent-first runtime authority section
   - Keep collection schemas, invariants, index_version rules unchanged
   - Add "Runtime planning (target)" vs "Current implementation (legacy)" if code not yet migrated

3. **docs/census-21-reframe.md**
   - Add top banner: interim table-resume fix inside legacy graph; not target architecture
   - Link to agent-first-grounded-planning.md

4. **docs/track-2_framework.md**
   - Reconcile "deterministic planning" steps with scaffolding principle
   - Explicit: temporal/benchmark/comparison math = deterministic; retrieval/table/geo selection = agent

5. **docs/typed_contracts.md**
   - Reframe: typed contracts = harness language, not replacement for agent reasoning

6. **README.md / USAGE_GUIDE.md** (if applicable)
   - Describe user experience: agent may ask clarifying questions; defaults to broad measures; suggests follow-ups

7. **app_description/CENSUS_DISCUSSION.md**
   - Add short "Runtime ownership (target)" section: this doc describes the **decision space for agent API composition**; agent executes multi-step tool loops; Chroma collections support groups-then-variables retrieval
   - Cross-link to agent-first-grounded-planning.md
   - Do not rewrite the Census API reference tables/examples — preserve depth

### Phase 4 — Cursor rules and Jira templates

Check .cursor/rules/general.mdc, jira-ticket-workflow.mdc, docs/jira-ticket-structure.md:
- Ticket templates should not default to "fix geography_node selector"
- Workflow should allow "agent planning shift" epics
- Remove any rule that implies regex analyzer or planner allowlists as preferred fix path

### Phase 5 — Consistency checklist (output)

After edits, verify:

- [ ] No architecture doc claims agent is owner while describing agent skip on clarification
- [ ] Every mention of geography_node clarifies legacy vs target role
- [ ] Chroma docs distinguish index/build (deterministic IDs) from runtime retrieval (agent semantic query)
- [ ] CENSUS-21 and similar tickets framed as plumbing on migration path, not end state
- [ ] Golden URL docs distinguish URL replay harness (deterministic ID replay) from NL UX (agent-first)
- [ ] track-2 "deterministic" scoped to contracts + comparison compute, not retrieval
- [ ] Docs state agent **composes and executes** Census API calls (not just "calls API" after planner)
- [ ] CENSUS_DISCUSSION.md linked as domain model for API parameter reasoning and multi-call loops

### Phase 6 — Deliverables

1. Commit-ready markdown edits (or a single PR draft description listing all file changes)
2. `docs/DOC_ALIGNMENT_CHANGELOG.md` summarizing what changed and what implementation tickets remain
3. Suggested Jira epic: "Agent-first grounded planning migration" with phases from agent-first-grounded-planning.md

## Constraints

- Do NOT edit *.plan.md files in .cursor/plans unless asked
- Do NOT change Python code in this pass
- Preserve ops/runbook accuracy (index rebuild, partitions, Chroma paths)
- Be direct: call out "documentation drift" and "planner-first implementation" explicitly
- When unsure, cite file:line evidence

## Success criteria

A new contributor reading only docs/ and app_description/ARCHITECTURE.md understands:
1. Agent reasons, retrieves semantically, **composes Census API parameters**, and **executes** tools (multi-call when needed)
2. CENSUS_DISCUSSION.md describes the category/geo/variable decision space for that composition
3. Harness validates grounded IDs before/after fetch — does not replace agent reasoning
4. Current code may still use legacy geography_node + immutable GroundedCensusPlan — migration in progress
5. Deterministic = typed safety + comparison math, NOT regex search or upstream URL assembly replacing the agent
```

---

## Notes for the human running this prompt

- Run in Agent mode with write access to markdown files.
- Review Phase 1 inventory before approving Phase 3 bulk rewrites.
- After doc alignment, implementation epics should follow phases in `agent-first-grounded-planning.md` § Migration phases.
- Keep `docs/chroma_geography_operator_runbook.md` ops content; only add a short "Runtime planning" pointer to the target doc.

---

## Why this prompt exists

The project repeatedly drifted toward **planner-first deterministic search** (regex analyzer, score-ranked selection, pre-agent graph halt) despite stated intent that **deterministic layers harness the agent**. Documentation mixed both messages, which reinforced the wrong implementation path in tickets (e.g. allowlists, geography_node selector fixes). This alignment pass makes the agent-first model explicit and marks legacy planner paths as migration debt.
