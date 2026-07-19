# Golden URL Validation Artifacts

This directory stores outputs from the post-LangGraph golden URL validation harness.

## Source fixture

- [test_questions/test_questions_new.csv](../../test_questions/test_questions_new.csv) — 70 rows with friendly questions and expected Census URLs

## Tiers

| Tier | Test module | Keys | CI |
|------|-------------|------|-----|
| 1 | `app_test_scripts/test_golden_census_urls.py` | none | yes |
| 2 | `app_test_scripts/test_golden_census_url_smoke.py` | `CENSUS_API_KEY` | no |
| 3 | `app_test_scripts/test_nl_questions_with_urls.py` | both API keys | no |

## Commands

```bash
# Tier 1 (offline rebuild contract)
uv run pytest app_test_scripts/test_census_url_fixtures.py app_test_scripts/test_golden_census_urls.py -q

# Tier 2 (direct HTTP smoke)
uv run pytest app_test_scripts/test_golden_census_url_smoke.py -m integration -q

# Tier 3 (NL E2E collection — no composite asserts)
$env:CENSUS_GOLDEN_COLLECT="1"
uv run pytest app_test_scripts/test_nl_questions_with_urls.py -m "integration and slow" -q

# Export summary + backlog from latest JSON artifacts
uv run python app_test_scripts/export_golden_url_report.py
```

## Verdict model

- **url_verdict** — any successful API call matches golden URL semantically (retries/failed attempts ignored)
- **delivery_verdict** — user-visible answer/data acceptable
- **composite** — derived; `false_failure` means good URL but bad delivery (P0)

## Artifact files

- `tier1_baseline_YYYYMMDD.json`
- `tier2_smoke_YYYYMMDD.json`
- `tier3_e2e_YYYYMMDD.json` / `.csv`
- `SUMMARY_YYYYMMDD.md`
- `backlog_YYYYMMDD.csv`

## Manual gate (until Fix PR B)

See [manual_multiturn_log.md](manual_multiturn_log.md) for the row 3 county/CA → `"all of them."` scenario.

## Fix PR planning

See [fix_pr_backlog_plan.md](fix_pr_backlog_plan.md) for triage buckets after baseline capture.
