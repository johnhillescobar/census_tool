# Documentation alignment changelog — agent-first grounded planning

**Date:** 2026-08-08  
**Scope:** Markdown only (Phase 0 doc alignment per [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md))  
**Authoritative target:** [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md)

## Summary

Reconciled architecture documentation so **agent-first** (reason → retrieve → **compose API params** → **execute** tools → analyze) is explicit, and **planner-first** paths (`geography_node`, score-select, agent skip on clarification) are labeled **legacy / migration debt**. Deterministic code is framed as **harness** (contracts, validation, comparison math), not retrieval or API composition authority.

## Files changed (this pass)

| File | Action |
| --- | --- |
| `app_description/ARCHITECTURE.md` | **Rewrite** — target vs legacy graphs, runtime planning table, legacy planner section |
| `docs/chroma_geography_architecture.md` | **Rewrite** — runtime target vs legacy; index build vs agent retrieval |
| `docs/census-21-reframe.md` | **Banner** — interim legacy-graph fix, not end state |
| `docs/track-2_framework.md` | **Clarify** — deterministic = harness; retrieval/API = agent |
| `docs/typed_contracts.md` | **Reframe** — typed harness, not planner replacement |
| `README.md` | **Rewrite** architecture section; user-facing legacy note |
| `USAGE_GUIDE.md` | **Rewrite** — expectations, current vs target graph |
| `app_description/CENSUS_DISCUSSION.md` | **Add** runtime ownership banner (API reference preserved) |
| `ARCHITECTURE_GUIDE.md` | **Banner + graph fix** — target vs legacy flow |
| `migration_evidence/golden_urls/fix_pr_backlog_plan.md` | **Banner** — replay harness vs NL UX |
| `migration_evidence/golden_urls/README.md` | **Clarify** Tier 1 replay vs Tier 3 NL |
| `docs/chroma_geography_debug_queries.md` | **Qualify** geography_node as legacy path |
| `.vscode/geography-breakpoints.md` | **Banner** — legacy breakpoint map |
| `.cursor/rules/general.mdc` | **Add** agent-first ticket guidance |
| `.cursor/rules/jira-ticket-workflow.mdc` | **Add** migration epic preference |
| `docs/jira-ticket-structure.md` | **Add** agent-first migration tier + references |

## Phase 1 inventory (all repo `*.md` scanned)

| Path | Stance | Conflict | Action | Priority |
| --- | --- | --- | --- | --- |
| `docs/agent-first-grounded-planning.md` | agent-first | — (authoritative) | no change | — |
| `docs/prompts/doc-alignment-agentic-shift.md` | agent-first | — (meta prompt) | no change | — |
| `app_description/ARCHITECTURE.md` | mixed → agent-first | Claimed agent execution owner while describing pre-agent `geography_node` planner | rewrite | P0 |
| `docs/chroma_geography_architecture.md` | planner-first → mixed | "`geography_node` is the only geography planning entry point" | rewrite | P0 |
| `docs/census-21-reframe.md` | planner-first | Documents planner halt/resume as primary fix path | add banner | P0 |
| `docs/track-2_framework.md` | mixed | Step 4 "deterministic planning flow" without agent retrieval scope | clarify | P0 |
| `docs/typed_contracts.md` | mixed | "deterministic planning layer" / same input → same plan | reframe | P0 |
| `README.md` | mixed | Agent owner + geography-first graph without legacy label | rewrite | P0 |
| `USAGE_GUIDE.md` | mixed | Outdated 4-node graph; "fully operational agent-first" | rewrite | P0 |
| `app_description/CENSUS_DISCUSSION.md` | domain | API reference only; no runtime owner | add section | P0 |
| `ARCHITECTURE_GUIDE.md` | mixed | Wrong node order; planning nodes as primary | banner + fix | P1 |
| `migration_evidence/golden_urls/fix_pr_backlog_plan.md` | mixed | CENSUS-21 as end-state fix | add banner | P0 |
| `migration_evidence/golden_urls/README.md` | ops-only | "deterministic replay" without NL distinction | clarify | P1 |
| `docs/chroma_geography_operator_runbook.md` | ops-only | Accurate index ops | no change | P2 |
| `docs/chroma_geography_debug_queries.md` | mixed | References geography_node as app path | qualify | P2 |
| `.vscode/geography-breakpoints.md` | planner-first | Planner path as only debug map | add banner | P2 |
| `docs/jira-ticket-structure.md` | ops-only | No agent migration epic tier | add row | P1 |
| `.cursor/rules/general.mdc` | ops-only | No agent-first ticket guard | add note | P1 |
| `.cursor/rules/jira-ticket-workflow.mdc` | ops-only | No migration epic guidance | add section | P1 |
| `migration_evidence/tract2_baseline_20260307/ownership_decomposition_map.md` | historical | "Deterministic Planning Ownership" as authority | deprecate mentally | P2 |
| `migration_evidence/tract2_baseline_20260307/contract_gap_register.md` | historical | Track 2 deterministic planning layer title | no change | P2 |
| `migration_evidence/baseline_20260718/BASELINE.md` | historical | Snapshot of legacy graph behavior | no change | P2 |
| `app_description/output_format_docs/AGENT_OUTPUT_FORMAT.md` | agent-first | Agent output contract only | no change | P2 |
| `app_description/geography_summaries/*.md` | domain | Category reference tables | no change | P2 |
| `app_description/langchain_migration/LANGCHAIN_V1_MIGRATION_PLAN.md` | historical | Pre-Chroma migration | no change | P2 |
| `docs/phase1-common-errors-and-advice.md` | ops-only | General advice | no change | P2 |
| `src/locations/README.md` | ops-only | Reference data | no change | P2 |
| `.github/pull_request_template.md` | ops-only | Generic template | no change | P2 |
| `.release_notes/RELEASE_NOTES_v0.0.1.md` | historical | Release snapshot | no change | P2 |
| Other `migration_evidence/**` manifests | historical | Baseline evidence | no change | P2 |

## Terminology glossary (use consistently)

| Term | Definition |
| --- | --- |
| **Agent-first** | Agent reasons, retrieves, **composes API params**, **executes** Census tools (possibly many times), analyzes, narrates |
| **Harness** | Reliability scaffolding at trust boundaries: validators, typed contracts, traces, fail-closed guards, deterministic comparison math — **constrain** the agent, **do not replace** reasoning, retrieval, API composition, or multi-call loops |
| **Lose as authority** | Stop using as runtime decision-maker; mark **Legacy / migration debt** in docs; do not extend; refactor to harness or remove from graph in implementation phases — **not** immediate code deletion in this doc pass |
| **Grounded** | Candidate IDs / enumerated geo codes from Chroma or Census list tools — agent may not invent FIPS or table codes |
| **API composition** | Agent builds `get`/`for`/`in`/dataset path per `CENSUS_DISCUSSION.md`; not planner-emitted frozen URL |
| **Multi-call loop** | Agent iterates tools until enough evidence to answer (enumerate → disambiguate → fetch → optional refetch) |
| **Planner-first (LEGACY)** | `geography_node` + analyzer + score-select before agent — migration debt |
| **Clarification** | Agent-driven dialogue with grounded options, not deterministic halt with `agent: skipped` |

**Banned or qualified in architecture docs:**
- "deterministic planning layer" → unless scoped to contracts + math only
- "geography_node is the only entry point" → legacy; target is agent tools + validator
- "no LLM geography resolver" → no **ungrounded** LLM geo codes; agent may resolve among grounded candidates
- "same input → same plan" → same **grounded ID choices** → same validated plan; agent wording may vary

## Phase 5 consistency checklist

- [x] No architecture doc claims agent is owner **without** labeling legacy agent skip on clarification (`ARCHITECTURE.md`, `README.md`, `USAGE_GUIDE.md`, `ARCHITECTURE_GUIDE.md`)
- [x] Every updated mention of `geography_node` clarifies legacy vs target role
- [x] Chroma docs distinguish index/build (deterministic IDs) from runtime retrieval (agent semantic query)
- [x] CENSUS-21 framed as plumbing on migration path, not end state
- [x] Golden URL docs distinguish URL replay harness from NL UX
- [x] track-2 "deterministic" scoped to contracts + comparison compute, not retrieval
- [x] Docs state agent **composes and executes** Census API calls
- [x] `CENSUS_DISCUSSION.md` linked as domain model for API parameter reasoning

## Implementation tickets remaining (code — not this pass)

From [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md) migration phases:

| Phase | Scope | Success signal |
| --- | --- | --- |
| **1. Agent planning turn** | After `temporal`, agent with retrieval tools only; no API until plan validated | No `agent: skipped` on table ambiguity |
| **2. Validator harness** | Replace `geography_node` authority with `validate_grounded_plan` gate | Invented IDs fail; agent can recover |
| **3. Agent clarification** | Merge `geography_resume` into agent checkpoint flow | Conversational two-turn table/geo |
| **4. Retire planner select** | Demote `select_grounded_plan` to proposed-ID checker | No score-rank in production path |
| **5. Index metadata** | Table category, universe, breadth in Chroma for agent defaults | Broad population ≠ housing false positives |

**Interim (keep, do not treat as architecture):** CENSUS-21 table-slot resume in legacy graph.

## Suggested Jira epic

**Title:** Agent-first grounded planning migration  
**Type:** Epic  
**Source of truth:** [`docs/agent-first-grounded-planning.md`](agent-first-grounded-planning.md)

**Description (draft):**

Migrate the Census Tool graph from planner-first (`geography_node` retrieve + score-select + halt, agent skip on clarification) to agent-first grounded planning: agent owns semantic Chroma retrieval, table/geo/category selection, Census API parameter composition, and multi-call tool execution; harness (typed contracts, `validate_grounded_plan`, strict Census API tool, `RetrievalTrace`, comparison math) fail-closes on ungrounded IDs only.

**Child tickets (suggested):**

1. Phase 1 — Agent planning turn after temporal (retrieval tools only)
2. Phase 2 — Validator harness node; demote `geography_node` to harness
3. Phase 3 — Agent-driven clarification; remove pre-agent agent skip
4. Phase 4 — Retire `select_grounded_plan` score-rank in production path
5. Phase 5 — Chroma metadata for breadth-first agent defaults
6. Doc alignment — **Done (this pass)**

**Out of scope for epic:** Deleting legacy modules until agent path passes golden Tier 3 NL acceptance documented separately.

## PR description draft

```
docs: align architecture docs to agent-first grounded planning

- Rewrite app_description/ARCHITECTURE.md and chroma_geography_architecture.md
  with target vs legacy graph split
- Reframe typed_contracts, track-2_framework, README, USAGE_GUIDE
- Add CENSUS-21 interim banner; golden URL replay vs NL UX notes
- Update Cursor rules and Jira structure for migration epic preference
- Add docs/DOC_ALIGNMENT_CHANGELOG.md

No Python changes. Implementation phases 1–5 remain open.
```
