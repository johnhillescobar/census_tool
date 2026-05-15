# Census Tool — Spec

This is the **bootstrap-SLIM** Spec leg (Spec → Layout → Implement → Monitor).
It is an **index**, not a place for new content. When goals/features/boundaries
change, edit here AND open a track plan if the change requires migration work.
If a section here contradicts code, that is drift — log it under D-IDs in
[.cursor/skills/drift-audit/references/known-regressions.md](.cursor/skills/drift-audit/references/known-regressions.md).

> **Naming note.** This repo uses two unrelated disciplines that share the
> acronym SLIM. **bootstrap-SLIM** (Spec/Layout/Implement/Monitor) is the
> project-organization framing used by `SPEC.md` and `AGENTS.md`. The
> **refactor-SLIM** skill at `.cursor/skills/slim/SKILL.md` is an unrelated
> legacy-code refactoring discipline (Seams/Learning-tests/Incremental/Mocking).
> When in doubt, "the SLIM skill" always means refactor-SLIM.

## Goal

A natural-language interface to U.S. Census Bureau data. The user asks
"what's the population of X" or "compare median income across counties in Y"
in plain English; the system resolves geography, picks variables, queries
the Census API, and returns a typed answer with optional charts/tables/PDF.

## Data source

- U.S. Census Bureau API (<https://api.census.gov>)
- Datasets: `acs/acs5`, `acs/acs1`, `acs/acsse` (others as needed)
- All responses are validated through `StrictCensusApiResponse`
  (`src/domain/census_tool_contract.py`) before entering workflow state.

## Key features

- Natural-language → typed query plan (deterministic where possible)
- Geography resolution (state, county, place, MSA — supported list in
  `config.py`)
- Variable validation against the Census variable catalog
- Multi-year temporal queries (point-in-time, range, rolling — see
  `TemporalIntent`)
- Benchmark/comparison reports (`BenchmarkIntent`, `ComparisonPlan`)
- Chart + table generation as side outputs (**tabular derivation centralized in [`src/services/census_render_adapter.py`](src/services/census_render_adapter.py)** — payload → dataframe → CSV/Parquet export helpers consumed by downstream tools)
- Session PDF export
- CLI (`main.py`) and browser UI (`streamlit_app.py`)

## Non-goals (explicit boundaries)

- No write-back to Census APIs.
- No non-U.S. geographies.
- No real-time data streaming (all responses are point-in-time queries).
- **No LLM math.** Derived metrics (differences, ratios, percent changes,
  benchmark comparisons) are computed by deterministic Python in
  `src/services/comparison_metric_compute.py`, never by model text.
- **Math is reached via tools, not LLM reasoning.** Long-term direction:
  expose deterministic math as a registered agent tool (LangChain
  `BaseTool`), not just as a workflow node. Today it lives in
  `src/workflows/comparison_metrics.py` (node) — moving it behind a tool
  is on the migration backlog.
- No model fallback for evidence-required outputs (Track 3+ enforces this).

## Architecture status

- **Track 2 — Deterministic Planning Layer** gate set (2A–2D) is **closed**.
  Latest closeout: Track 2D
  [migration_evidence/track2_progress_20260511/track2d_closeout.md](migration_evidence/track2_progress_20260511/track2d_closeout.md).
  **Next active track:** Track 3 — Provenance Enforcement (see
  [.cursor/plans/v2-track3-provenance-enforcement.plan.md](.cursor/plans/v2-track3-provenance-enforcement.plan.md)).
- Migration plan:
  [.cursor/plans/full-v2-architecture-migration.plan.md](.cursor/plans/full-v2-architecture-migration.plan.md)
- Per-track plans: see [.cursor/plans/](.cursor/plans/)
  (`v2-track1` through `v2-track4`)
- Latest drift audit:
  [migration_evidence/track2_progress_20260426/drift_audit.md](migration_evidence/track2_progress_20260426/drift_audit.md)

## Migration discipline (non-negotiable)

This is a long-running migration. To prevent perpetual refactor:

1. **One active track at a time.** Track N+1 does not open until Track N's
   exit criteria pass (see
   [.cursor/skills/census-v2-tech-lead/track-gates.md](.cursor/skills/census-v2-tech-lead/track-gates.md)).
2. **No ad-hoc sub-plans.** All migration work is a TODO inside an existing
   track plan. If new work is discovered mid-track, add it to the current
   track's plan with a track-prefixed ID (e.g. `t2-N`), do not spawn a
   separate `<topic>_<hash>.plan.md`.
3. **Drift audit before track exit.** A track cannot be marked complete
   until `/drift-audit` runs clean (no new RED findings vs the prior
   baseline) and the report is written to `migration_evidence/`.
4. **Sub-plans already in flight stay folded back in.** The
   `strict_census_artifacts` sub-plan in `~/.cursor/plans/` was opened
   outside Track 2's plan. Its 9 open items belong inside Track 2 and
   should be migrated there before further work continues on them.

## Where to read more

- Architecture overview:
  [app_description/ARCHITECTURE.md](app_description/ARCHITECTURE.md)
- Output format:
  [app_description/output_format_docs/AGENT_OUTPUT_FORMAT.md](app_description/output_format_docs/AGENT_OUTPUT_FORMAT.md)
- Typed contracts catalog: [docs/typed_contracts.md](docs/typed_contracts.md)
- Usage / examples: [USAGE_GUIDE.md](USAGE_GUIDE.md)
- Architecture deep-dive: [ARCHITECTURE_GUIDE.md](ARCHITECTURE_GUIDE.md)
  ⚠️ has known doc drift (D2, D5 — see drift-audit catalog)

## Companion file

- [AGENTS.md](AGENTS.md) — **bootstrap-SLIM** Layout leg. Stack, folder rules,
  working modes, drift policy.
