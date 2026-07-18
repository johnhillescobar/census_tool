# Runtime Modernization Baseline — 2026-07-18

## Dependency pins (pre-migration)

| Package | pyproject.toml | uv.lock |
|---------|----------------|---------|
| langchain | ==0.3.27 | 0.3.27 |
| langgraph | >=0.6.7 | 0.6.7 |
| langchain-core | >=0.3.75 | 0.3.79 |

## Graph topology (actual)

```
memory_load → geography → temporal → benchmark → comparison → agent → comparison_metrics → output → memory_write
```

- **Thread checkpoints:** SQLite `checkpoints.db` via LangGraph `SqliteSaver`
- **User memory:** JSON files `memory/user_{id}.json` via `memory_load` / `memory_write`
- **Track 3 provenance:** Not complete (`EvidenceBundle` / provenance gate outstanding)

## Baseline test evidence

```bash
uv run ruff check src app_test_scripts
uv run pytest app_test_scripts/ -m "not integration" -q
uv run pytest app_test_scripts/ -m integration -q   # requires OPENAI_API_KEY + CENSUS_API_KEY
```

Recorded offline baseline (Phase 0c complete): **297 passed**, 11 deselected (integration), 1 warning (`pytest.mark.slow` unregistered).

Phase 0c offline coverage:

- `app_test_scripts/test_phase0c_policy.py` — US default, explicit NYC, six-year execution spec, plan validator, renderability guard
- `app_test_scripts/test_geography_workflow_planning.py` — geography node routing and temporal preservation
- `app_test_scripts/test_typed_geography_state.py` — typed `CensusState.geo` coercion and memory projection

Credentialed integration gate (requires `OPENAI_API_KEY` + `CENSUS_API_KEY`):

```bash
uv run pytest app_test_scripts/test_integration_phase0c_query2.py -m integration -q
```

Not run in baseline capture environment (no API keys in CI shell). Run locally before B1 dependency upgrade.

## Golden scenarios (offline fixtures)

See `app_test_scripts/test_golden_agent_fixtures.py` for locked parser/plan contracts.

## Phase 0c geography/temporal execution policy

- **Geography node** (`src/workflows/geography.py`) runs before temporal; `geography_policy` resolves intent.
- **Missing geography** on measure/time queries defaults to US national (`geo_for={"us":"1"}`, `source="missing_geo_default"`).
- **Explicit geography** takes precedence; ambiguous explicit references (e.g. "New York City" without alias) → `GEOGRAPHY_AMBIGUOUS` clarification.
- **Temporal/benchmark nodes** preserve upstream `requires_clarification` from geography.
- **`ExecutionSpec`** derives required query years from temporal range (2015–2020 → six years).
- **`plan_result_validator`** strips charts/tables when agent output fails plan obligations or census data is not renderable.
- **`output_node`** gates chart/table rendering on `is_census_data_renderable()`.

## Phase 0c typed geography state

- `WorkflowPlan.geography` remains the authoritative resolution envelope (`GeographyResolved` / `GeographyClarificationRequired`).
- `CensusState.geo` is now a typed resolved projection: `GeographyIntent | None` (not `{}`).
- Legacy checkpoint `{}` geo payloads normalize to `None`; resolved legacy dicts coerce to `GeographyIntent`.
- JSON user memory still stores plain dicts via `geo_intent_to_dict()` at the memory boundary.
## Known defects addressed in Phase 0b/0c

1. `_normalize_error_response()` overwrites clarification text on `success: false`
2. `output_node` renders charts when `census_data` is truthy but empty
3. Missing geography defaults to hidden NYC in `geo_utils.DEFAULT_GEO` instead of US national policy
