# What I checked first
I searched your Track 2 plan, the full migration plan sections for deterministic planning/canonical suite, and your current src/domain, src/services, and src/workflows layout.

**Authoritative target (2026-08):** [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md) — agent reasons, retrieves, **composes API params**, **executes** Census tools (multi-call when needed); deterministic code is **harness only**.

# Non-negotiable migration intent
Typed contracts and workflow nodes are built to empower the reasoning node with deterministic, validated artifacts. They are reliability scaffolding for the reasoning node, not a replacement for reasoning-node task execution.

**Scope "deterministic" correctly:**
- **Harness (keep):** Pydantic contracts, temporal/benchmark/comparison **math**, fail-closed validation, retrieval traces, repeatable comparison formulas.
- **Agent-owned (not deterministic):** semantic Chroma retrieval, table/geo/category selection, Census API parameter composition, multi-call tool loops, clarification dialogue.

Do **NOT** use "deterministic planning layer" to mean regex search, score-rank auto-select, or pre-agent URL assembly. Those are **legacy planner-first** paths marked migration debt.

# Locked execution decision
- Canonical principle: deterministic contracts and workflow/service steps are reliability scaffolding that empower AI reasoning nodes/components and must not replace AI reasoning nodes/components.
- Temporal/benchmark/comparison nodes normalize time and comparison **math**; they may gate ambiguous **temporal/benchmark** input early — **not** replace agent retrieval or table/geo selection.
- The reasoning node remains the execution owner: composes Census API parameters, performs repeated strict typed Census tool calls as needed, and drives answer/table/chart directives.

What exists already

- Track 2 plan is clear on what to add (TemporalIntent, BenchmarkIntent, ComparisonPlan) but light on execution order details.
- Full plan adds the missing specifics (canonical queries, deterministic rules, pass criteria).
- Your repo already has target folders to place this work: src/domain, src/services, src/workflows.

# The actual problem
Problem: Track 2 is easy to start in the wrong order and accidentally mix in Track 3/4 concerns.
Evidence: the plan explicitly requires Track 1 gate, deterministic-only computation, canonical suite, and dependency freeze.

# Options

- Option A (safer): do Track 2 as a documentation/test-design pass first, then implementation.
- Option B (faster): implement contracts + planner immediately, then backfill tests/checklists.
- Option C (risky): jump to workflow wiring first (usually causes rework).

# My recommendation
Use **Option A**. Here is the step-by-step sequence to follow now (no code changes yet):

1. Confirm Track 1 gate is truly closed

    - Verify evidence that Track 1 exit criteria passed (behavior parity, no sys.path hacks, docs updated).
    - Output: a short “Track 2 start allowed” note in your migration evidence docs.

2. Write a one-page Track 2 scope guard

    - List what is in-scope: typed planning contracts, deterministic comparison compute, canonical - suite.
    - List what is out-of-scope: provenance gate behavior (Track 3), dependency upgrades/FastAPI/SSE (Track 4).
    - Output: checklist you can reuse in every PR review.

3. Define contract shape on paper first

    - For TemporalIntent, BenchmarkIntent, ComparisonPlan, decide required/optional fields and allowed  enums.
    - Explicitly decide how ambiguous inputs are represented (clarification-needed vs hard fail).
    - Output: contract table (field, type, allowed values, validation rule).

4. Design harness + agent responsibility matrix before coding

    - Map: raw request → temporal normalization (harness) → **agent** retrieval/table/geo/API composition → validate grounded plan (harness) → agent execute → deterministic comparison compute (harness).
    - Mark where each transformation lives (domain validation vs services logic vs workflows orchestration vs agent tools).
    - Explicitly verify each new node/service strengthens reasoning-node reliability and does **not** displace agent retrieval, API composition, or multi-call execution.
    - Explicitly verify locked execution behavior: harness clarifies/gates only at trust boundaries (contracts, math); reasoning node executes typed tool loops including Chroma search and Census fetches.
    - Output: node/service responsibility matrix (agent vs harness columns).

5. Define deterministic math rules explicitly

    - For each metric type (difference, pct_difference, rank, index_base_100), define exact formula and edge-case handling.
    - Decide fail behavior for divide-by-zero, missing years, missing benchmarks.
    - Output: “deterministic math spec” doc snippet.

6. Build canonical acceptance suite spec (test plan only)

Use canonical temporal + benchmark + failure queries from full plan.
For each query, define expected planning artifact behavior (not just final text).
Output: test case table with expected TemporalIntent/BenchmarkIntent/ComparisonPlan characteristics.

7. Define repeatability proof

    - Decide harness repeatability: same **grounded ID choices** run N times => same validated plan and API URLs (stable ordering included). Agent **wording** may vary.
    - Include one complex benchmark case and one agent-clarification case (grounded options, not raw enum dumps).
    - Output: repeatability protocol (what to run, what must be identical).

8. Dependency freeze checkpoint

    - Decide one explicit check for “no dependency upgrades during Track 2”.
    - Output: a gate item you run before merge.

# Track 2 policy decisions (locked)

1. Default when no temporal phrase is present:
   - `latest_available`

2. Temporal conflict handling:
   - Use a global ambiguity policy.
   - If temporal signals conflict in ways that can produce different valid plans, do not auto-resolve.
   - Fail to clarification with a deterministic clarification question.

3. Scope implication for Track 2:
   - Agent clarification behavior may require refactoring so the **agent** (not pre-agent planner halt) returns structured clarification with grounded options.
   - Track 2 in-scope: typed clarification contracts and harness fail-closed — **not** extending `geography_node` score-select or regex analyzer authority.
   - Provenance gate behavior remains out of scope for Track 2 (Track 3).
   - Long-term migration epic: **Agent-first grounded planning** — see [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md).
