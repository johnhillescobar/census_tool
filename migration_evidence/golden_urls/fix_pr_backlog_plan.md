# Fix PR Backlog Plan (from golden URL validation)

**Baseline captured:** 2026-07-18 — see [backlog_20260718.csv](backlog_20260718.csv) and [SUMMARY_20260718.md](SUMMARY_20260718.md).

## Triage summary (baseline)

| Priority | failure_class | row_no | status |
|----------|---------------|--------|--------|
| P0 | `geography_blocked` | 3 | Confirmed offline — zero API calls, `composite=blocked` |
| P0 | `clarification_resume_missing` | (manual) | Documented in [manual_multiturn_log.md](manual_multiturn_log.md) |
| — | Tier 1 rebuild | all 70 | Pass — no `tier1_builder_drift` |
| pending | Tier 2 smoke | all 70 | Requires local `CENSUS_API_KEY` |
| pending | Tier 3 NL E2E smoke | 12 rows | Requires `CENSUS_API_KEY` + `OPENAI_API_KEY` |

## P0 — Geography blocked

**Symptom:** `api_call_count=0`, `composite=blocked`, `failure_class=geography_blocked`

**Example:** Row 3 — `"Show total population for all California counties in 2023."`

**Fix PR A**
- File: [src/services/geography_policy.py](../../src/services/geography_policy.py)
- Change: When `infer_geo_context` returns `county` + state FIPS, compose `county:* in state:XX` instead of treating `"county"` and state name as competing candidates
- Regression: Tier 3 row 3 → `composite=pass`

## P0 — Clarification resume missing

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
