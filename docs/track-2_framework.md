# What I checked first
I searched your Track 2 plan, the full migration plan sections for deterministic planning/canonical suite, and your current src/domain, src/services, and src/workflows layout.

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

4. Design deterministic planning flow before coding

    - Map: raw request -> temporal normalization -> benchmark planning -> query expansion -> deterministic compute.
    - Mark where each transformation lives (domain validation vs services logic vs workflows orchestration).
    - Output: node/service responsibility matrix.

5. Define deterministic math rules explicitly

    - For each metric type (difference, pct_difference, rank, index_base_100), define exact formula and edge-case handling.
    - Decide fail behavior for divide-by-zero, missing years, missing benchmarks.
    - Output: “deterministic math spec” doc snippet.

6. Build canonical acceptance suite spec (test plan only)

Use canonical temporal + benchmark + failure queries from full plan.
For each query, define expected planning artifact behavior (not just final text).
Output: test case table with expected TemporalIntent/BenchmarkIntent/ComparisonPlan characteristics.

7. Define repeatability proof

    - Decide your deterministic assertion: same input run N times => same planning artifacts (stable ordering included).
    - Include one complex benchmark case and one failure-to-clarify case.
    - Output: repeatability protocol (what to run, what must be identical).

8. Dependency freeze checkpoint

    - Decide one explicit check for “no dependency upgrades during Track 2”.
    - Output: a gate item you run before merge.
