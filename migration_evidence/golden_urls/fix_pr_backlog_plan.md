# Fix PR Backlog Plan (from golden URL validation)

> **Architecture note:** Golden URL **Tier 1 / grounded replay** validates grounded candidate-ID contracts (URL replay harness) — deterministic ID replay, not planner auto-select policy. **Tier 3 NL UX** target is agent-first: agent retrieves, composes API params, executes tools. P0 fixes below patch the **legacy planner-first graph** on the migration path; see [`docs/agent-first-grounded-planning.md`](../../docs/agent-first-grounded-planning.md) and CENSUS-21 banner in [`docs/census-21-reframe.md`](../../docs/census-21-reframe.md).

**Baseline captured:** 2026-07-18 — see [backlog_20260718.csv](backlog_20260718.csv) and [SUMMARY_20260718.md](SUMMARY_20260718.md).

## Triage summary (baseline)

| Priority | failure_class | row_no | status |
|----------|---------------|--------|--------|
| P0 | `table_ambiguous` / stale `geography_blocked` | 3 | Turn 1 table clarify works; turn 2 resume continues geography (CENSUS-21) |
| P0 | `clarification_resume_missing` | (manual) | Documented in [manual_multiturn_log.md](manual_multiturn_log.md) |
| — | Tier 1 rebuild | all 70 | Pass — no `tier1_builder_drift` |
| pending | Tier 2 smoke | all 70 | Requires local `CENSUS_API_KEY` |
| pending | Tier 3 NL E2E smoke | 12 rows | Requires `CENSUS_API_KEY` + `OPENAI_API_KEY` |

## P0 — Row 3 table ambiguity (CENSUS-21)

**Symptom (2026-08-08):** `TABLE_AMBIGUOUS`, `requested_slot=table`, zero API calls. Geography retrieval never runs until table is locked. Turn-2 table resume was broken (`hierarchy_id` required before geography ran).

**Example:** Row 3 — `"Show total population for all California counties in 2023."`

**Fix PR A (CENSUS-21)** — *interim legacy-graph plumbing; not target architecture*
- Files: [src/workflows/geography.py](../../src/workflows/geography.py), [src/services/geography_clarification_resume.py](../../src/services/geography_clarification_resume.py)
- Change: Table-slot resume validates grounded `table_*` pick, locks table evidence, continues geography retrieval/selection/validation. No planner B01001/B01003 allowlist.
- Regression: [test_table_clarification_resume.py](../../app_test_scripts/test_table_clarification_resume.py), two-turn row 3 in [test_golden_url_offline_regressions.py](../../app_test_scripts/test_golden_url_offline_regressions.py)
- Success path: Turn 1 `TABLE_AMBIGUOUS` → Turn 2 table pick → `county:*` + `state:06` → agent

## P0 — Clarification resume missing (CENSUS-22)

**Symptom:** Turn 2 follow-up (`"all of them."`) re-clarifies or parses tokens as geographies

**Fix PR B**
- Files: [src/services/graph_session.py](../../src/services/graph_session.py), geography clarification resume handler
- Change: Preserve `original_query` and pending clarification options across delta turns; map option ids / "all of them" replies
- Regression: Two-turn manual scenario in [manual_multiturn_log.md](manual_multiturn_log.md)

## P0 — False failure (parser / delivery)

**Symptom:** `url_verdict=pass`, `composite=false_failure`, `failure_class=false_failure_parser`

**Fix PR C**
- File: [src/agents/census_query_agent.py](../../src/agents/census_query_agent.py)
- Change: Align `_has_invalid_geography` with last-success strict call semantics; do not fail delivery when a later successful API call exists
- Regression: Unit test in `test_census_url_fixtures.py` + Tier 3 smoke

## P1 — Tier 1 builder drift

**Symptom:** `tier1_baseline.json` entries with `failure_class=tier1_builder_drift`

**Fix PR D**
- Files: [src/clients/census_api_utils.py](../../src/clients/census_api_utils.py) and/or golden CSV
- Regression: `test_golden_url_rebuilds` for affected rows

## P1 — Agent wrong URL / no calls

**Symptom:** `composite=true_failure` or `pass_with_warnings` with `agent_wrong_url` / `agent_no_calls`

**Fix PR E+**
- Scope from backlog rows after P0 fixes
- One regression test per bucket

## Triage workflow

1. Run Tier 3 with `CENSUS_GOLDEN_COLLECT=1`
2. `uv run python app_test_scripts/export_golden_url_report.py`
3. Sort `backlog_YYYYMMDD.csv` by `priority`, then `composite`
4. Open one fix PR per `failure_class` bucket with a single regression test

**Per-ticket execution:** Read Jira ticket → reproduce / investigate → Plan mode if the fix path forks → implement → PR. Canonical write-up: [docs/jira-ticket-structure.md](../../docs/jira-ticket-structure.md#working-a-ticket-execution-workflow).
