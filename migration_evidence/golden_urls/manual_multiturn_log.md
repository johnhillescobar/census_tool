# Manual Multi-Turn Gate Log

Status: **known broken** (document before Fix PR B)

## Scenario

| Turn | User input | Expected |
|------|------------|----------|
| 1 | `Compare population by county in California` (CSV row 3 friendly question) | Resolve all CA counties; call golden URL |
| 2 | `all of them.` | Resume clarification; enumerate counties |

## Observed (2026-07-18, user `chiki`)

**Turn 1**
- `GEOGRAPHY_AMBIGUOUS` with options `geo_0: county`, `geo_1: California`
- Zero Census API calls
- Evidence: [memory/user_chiki.json](../../memory/user_chiki.json)

**Turn 2**
- Same clarification loop with two US defaults
- Logs: `Unable to resolve hint 'all'/'them'`

## Pass criteria (manual)

- [ ] Turn 1 reaches agent and calls URL equivalent to row 3 golden URL
- [ ] Turn 2 resolves follow-up without re-asking the same geography question
- [ ] Final answer references California county population data

## Automated coverage

- Tier 3 row 3 tags `blocked` / `geography_blocked` until Fix PR A
- Add two-turn pytest after Fix PR B in `test_nl_questions_with_urls.py`
