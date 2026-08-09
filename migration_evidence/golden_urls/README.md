# Golden URL acceptance

This directory stores release evidence for the temporal-first, Chroma-grounded Census graph.

## Corpus and verdicts

`test_questions/test_questions_new.csv` contains 124 friendly questions and expected Census URLs. **Grounded replay (Tier 1 harness)** validates 122 data rows through retrieved candidate IDs and plan validation — deterministic ID replay, not NL agent UX. Rows 9 and 10 are catalog URLs and are intentionally bypassed. **Tier 3** exercises full NL graph (agent-first target; legacy planner path may still apply).

- `url_verdict`: any successful Census call semantically matches the expected URL; failed retries are ignored.
- `delivery_verdict`: the user-visible answer and data are acceptable.
- `composite`: combines URL and delivery; `false_failure` means a correct URL with failed delivery.

## Acceptance tiers

| Tier | Scope | Credentials | CI |
| --- | --- | --- | --- |
| Grounded replay | all 124 questions, offline model-drift contract | none | yes |
| Tier 1 | offline URL reconstruction | none | yes |
| Tier 2 | direct Census HTTP smoke | `CENSUS_API_KEY` | no |
| Tier 3 | full graph and NL execution | LLM and Census keys | no |

Run grounded replay:

`uv run pytest app_test_scripts/test_phase6_golden_grounded_replay.py -q`

Run Tier 1:

`uv run pytest app_test_scripts/test_census_url_fixtures.py app_test_scripts/test_golden_census_urls.py -q`

Run Tier 2:

`uv run pytest app_test_scripts/test_golden_census_url_smoke.py -m integration -q`

Run the full 124-row Tier 3 collection:

`CENSUS_GOLDEN_COLLECT=1 CENSUS_GOLDEN_FULL_124=1 uv run pytest app_test_scripts/test_nl_questions_with_urls.py -m "integration and slow" -q`

Export the latest summary and backlog:

`uv run python app_test_scripts/export_golden_url_report.py`

Run release static and non-integration gates:

`uv run pytest app_test_scripts -m "not integration" -q`

`uv run ruff check . && uv run ruff format --check .`

## Artifacts

- `tier1_baseline_YYYYMMDD.json`
- `tier2_smoke_YYYYMMDD.json`
- `tier3_e2e_YYYYMMDD.json` and `.csv`
- `SUMMARY_YYYYMMDD.md`
- `backlog_YYYYMMDD.csv`

Every artifact must identify the corpus size and command. Never overwrite prior release evidence. Preserve failed attempts for
diagnosis, but determine URL equivalence from successful attempts only.
