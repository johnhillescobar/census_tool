# Jira ticket structure (Census Tool)

Canonical guide for writing and reviewing CENSUS backlog tickets. Use this when creating or updating issues in the [CENSUS project](https://johnhillescobar.atlassian.net/jira/software/projects/CENSUS/boards/36).

## Ticket tiers (rule of thumb)

| Tier | When required | When recommended | Typical sections |
|------|---------------|------------------|------------------|
| **Card** | Never for P0 runtime or production-gating work | Optional polish: env docs, SDK wiring, `.env.example` | Context (2–3 sentences), Tasks, Acceptance criteria |
| **Regular spec** | Medium infra/hosting tasks with one obvious path | Tier 2 services (Docker, Sentry, LangSmith) | Context, Why this matters, Tasks, Acceptance criteria; Options = "No fork — follow pattern X" |
| **Full spec (hybrid)** | P0 bugs, provenance gates, API contracts, anything safety- or release-critical | Runtime geography/clarification work while the app cannot answer real questions | All five hybrid sections below |
| **Contract-led** | Ratified build slices where design is closed (e.g. Track 3 provenance vocabulary, large schema manifests) | Large "implement the spec doc" efforts | Goal + source of truth in Context; closed contract in Tasks; Options only if implementation path forks |

**Default for this repo today:** Geography/runtime bugs under [CENSUS-20](https://johnhillescobar.atlassian.net/browse/CENSUS-20) → **full spec hybrid**. Production readiness under CENSUS-1 → **regular spec or full hybrid** by risk. Delivery/docs under CENSUS-2 → **card or regular spec**.

## Hybrid structure (default for P0 / high-risk)

Use these five sections in order. Fold dependencies and requirements into the sections below—do not add separate Requirements or Dependencies headings unless the ticket is contract-led.

### 1. Context

**Scope:** What is true today—repro, evidence, file paths, parent/related keys, current workaround, what is *not* the code path (e.g. retired modules).

**Stop when:** You start arguing priority or listing fixes.

**Litmus test:** Can someone locate and reproduce the issue from this section alone?

### 2. Why this matters

**Scope:** User-visible impact, correctness/safety stake, release blocker, cost of shipping the workaround.

**Stop when:** You start listing solution options.

**Litmus test:** Would a reviewer agree this should be done before production or before the next epic?

### 3. Options for the real fix

**Scope:** 2–3 viable approaches with tradeoffs; what was deferred elsewhere; what **this ticket** will implement.

**Skip or shorten:** When only one path exists—write: `No fork — follow existing pattern in \`path\`.` 

**Litmus test:** Would picking the wrong option waste days? If no, use one line.

### 4. Tasks

**Scope:** Ordered **how** to implement—files to touch, tests to add, docs to update, sequencing (including dependency on other keys inline).

**Not:** Restating outcomes ("tests pass")—those belong in Acceptance criteria.

**Litmus test:** Could an assignee execute without guessing order?

### 5. Acceptance criteria

**Scope:** Verifiable **definition of done**—pytest commands, golden rows, manual scenarios, CI gates, doc links.

**Not:** Implementation steps.

**Litmus test:** Can QA or the author say pass/fail without reading Tasks?

## WHAT / HOW / PROOF (anti-duplication rule)

| Kind | Section |
|------|---------|
| Behavior the system must satisfy | Context + Why (stakes) and Tasks (constraints inline) |
| Steps to build it | Tasks |
| Proof it works | Acceptance criteria |

## When to use each tier (Census examples)

| Work | Tier | Example keys |
|------|------|--------------|
| App unusable / golden URL P0 | Full spec hybrid | CENSUS-21–24 |
| Agent-first planning migration (graph refactor) | Full spec hybrid or contract-led | New epic — see `docs/agent-first-grounded-planning.md` phases 1–5 |
| Provenance gate, FastAPI production contract | Full spec hybrid | CENSUS-7, CENSUS-27 |
| FastAPI graph tests, Postgres checkpoints | Regular spec | CENSUS-26, CENSUS-32 |
| LangSmith, Sentry, secrets doc | Card or regular spec | CENSUS-30, CENSUS-31, CENSUS-35 |
| Post-P0 backlog triage | Regular spec | CENSUS-25 |
| Cancelled / superseded | Close with comment; do not rewrite body unless reopening | CENSUS-28, CENSUS-29 |

## Contract-led variant (ratified design only)

Use when implementing an already-ratified spec—not greenfield design.

```markdown
## Context
Goal: [one-line outcome]
Source of truth: [doc path — canonical, not Jira]
Pattern to follow: [existing file/module]

## Why this matters
[Why executing the contract now unblocks release or other work]

## Options for the real fix
[Usually: "No fork — implement ratified spec." OR enum/storage fork with dependency called out]

## Tasks
[Implement contract; link to doc section—not duplicate full table in Jira if doc is canonical]

## Acceptance criteria
[Local verification commands; typecheck; migration apply; etc.]
```

Keep large inventories (table lists, enum registries) in repo docs; Jira links to them.

## Working a ticket (execution workflow)

Use this sequence when picking up a CENSUS issue. Do not skip straight to implementation for P0 bugs—the ticket's Context may assume a root cause that reproduction disproves (e.g. `geography_blocked` vs table-slot ambiguity on golden row 3).

### Pipeline

```
Read ticket → Reproduce / investigate → Plan (if fork) → Implement → PR
```

| Step | Always? | What to do |
|------|---------|------------|
| **Read ticket** | Yes | Full Jira hybrid spec (Context → Acceptance criteria). Note related keys, retired paths, and proof commands. |
| **Reproduce / investigate** | Yes for P0 bugs | Run debug scripts and targeted pytest from Acceptance criteria; grep/read cited files before proposing changes. |
| **Plan mode** | When needed | Short planning pass *after* repro, before code. See triggers below. |
| **Implement** | After above | Smallest correct diff; one ticket → one PR unless you explicitly merge overlapping fixes. |
| **PR** | Per fix ticket | One regression test per `failure_class` bucket where applicable; see [fix_pr_backlog_plan.md](../migration_evidence/golden_urls/fix_pr_backlog_plan.md). |

### When to use Plan mode

Use Cursor Plan mode (or an equivalent design pass) **after reproduction**, not before:

- **2+ viable fix paths** named in Options, or repro contradicts the ticket assumption.
- **Multi-ticket overlap** (e.g. CENSUS-21 vs CENSUS-24 on the same golden row)—decide one PR vs two before coding.
- **Checkpoint / resume contracts** (e.g. CENSUS-22 depends on turn-1 pending state from prior fixes).

Skip Plan mode when the ticket already picked the approach and scope is narrow (typical for copy/id fixes, single-function parser changes, or infra wiring with one obvious path).

### One ticket → one PR

| Ticket kind | PR? |
|-------------|-----|
| P0 fix (CENSUS-21–24, CENSUS-23, …) | Yes — one PR each, smallest diff that satisfies Acceptance criteria |
| Triage only (CENSUS-25) | No code PR — output is new Jira bugs / backlog rows |
| Infra / observability (Phase B) | Yes — read → plan → implement often fits better than bug repro |

**Overlap exception:** If one root cause satisfies two tickets (e.g. row 3 table-slot fix closes both geography-block symptoms and CENSUS-24 copy), either land one PR that closes both with both regression tests, or land the dependency ticket first and keep the second PR minimal.

### Learning project note

This repo is a learning project: investigate and propose before writing code unless the assignee says **"write the code"** or **"implement."** Commits and PRs only when explicitly requested.

## References

- **Agent-first target architecture:** `docs/agent-first-grounded-planning.md`
- Golden URL evidence: `migration_evidence/golden_urls/`
- Architecture: `app_description/ARCHITECTURE.md`, `ARCHITECTURE_GUIDE.md`
- Census API domain model: `app_description/CENSUS_DISCUSSION.md`
- Agent/playbook audit: `.cursor/` rules and skills
