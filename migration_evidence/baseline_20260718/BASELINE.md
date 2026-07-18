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

## Lint gate (required every PR)

Every phase and every PR must pass a **full-repository** ruff check with zero errors:

```bash
uv run ruff check src app_test_scripts
```

Do not scope lint to changed paths only; unscoped issues increment across phases.

Prompt/Census-literal files with intentional long lines use `per-file-ignores` for E501 in
`pyproject.toml` (not silent debt). All other files must stay within line-length without ignores.

Evidence (2026-07-18): **0 errors** from `uv run ruff check src app_test_scripts`.

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

## B1 — LangChain/LangGraph dependency upgrade

- Upgraded to LangChain 1.x / LangGraph 1.x family in `pyproject.toml`. Classic `langchain-classic` rollback removed after A4 cutover.
- `langchain_core.callbacks.manager` import retained in `strict_census_api_tool.py` where needed.
- Added `tf-keras` for transitive `sentence_transformers` / Keras 3 compatibility on Windows.

Evidence (2026-07-18):

```bash
uv run ruff check src app_test_scripts
uv run pytest app_test_scripts/ -m "not integration" -q
```

Result: **316 passed**, 13 deselected (integration), **full-repo ruff clean** (see Lint gate above).

## B2 — Durable SQLite threads and delta invokes

- `checkpoints.db` retained by default; deleted only when `CENSUS_RESET_CHECKPOINTS=1`.
- `src/services/graph_session.py`: UUID thread IDs, `build_fresh_thread_state`, `build_delta_turn_state`, `build_turn_state`, turn-reset artifacts.
- `main.py` / `streamlit_app.py`: UUID-scoped threads, delta invokes on turn 2+, Streamlit “New conversation” (rotates UUID, resets `turn_count`, clears UI history).
- `CensusState.artifacts` reducer clears merged artifacts at turn boundary via `__turn_reset__`; `plan` / `final` / `error` use overwrite reducers cleared in delta state.
- JSON user memory unchanged (`memory_load` / `memory_write`).

Tests: `app_test_scripts/test_graph_session.py` (4), `app_test_scripts/test_checkpoint_persistence.py` (5) against temp SQLite via `CENSUS_CHECKPOINT_DB`.

Evidence (2026-07-18):

```bash
uv run ruff check src app_test_scripts
uv run pytest app_test_scripts/test_graph_session.py app_test_scripts/test_checkpoint_persistence.py -q
uv run pytest app_test_scripts/ -m "not integration" -q
```

Result: **322 passed**, 13 deselected; B2 checkpoint tests **9 passed**.

## A1–A2 — Runtime seam and modern backend

- `src/agents/runtime/`: `AgentExecutionResult`, `ModernBackend` (`create_agent` + call-limit middleware), `factory.py`.
- `CensusQueryAgent.solve()` invokes `self.backend.invoke()`; workflow node remains runtime-unaware.
- `src/agents/adapters/message_to_executor.py` maps message traces to legacy `{output, intermediate_steps}`.

Tests: `test_census_query_agent_runtime.py`, `test_modern_backend.py`, `test_agent_runtime_factory.py`, `test_message_to_executor.py`.

## A3 — Modern runtime contract parity

- Offline adapter + shared-parser parity fixtures: `test_agent_runtime_parity.py` (success, clarification, invalid geography).
- Credentialed modern smoke: `test_agent_runtime_integration.py` (skipped without API keys).

## A4 — Cutover (classic removed)

- `AGENT_RUNTIME=classic` rejected with explicit error; default/unset uses modern only.
- Removed `langchain-classic`, `ClassicBackend`, `AgentExecutor`, and ReAct prompt wiring from `CensusQueryAgent`.
- Offline pytest autouse clears `AGENT_RUNTIME` so tests run on modern.

## Phase 5 — FastAPI/SSE adapter

- `src/api/contracts.py`: typed `QueryRequest`, `QueryResponse`, `HealthResponse`.
- `src/api/fastapi_app.py`: `/health`, `/query`, `/query/stream` (SSE over graph invoke; checkpoint-aware thread handling).
- CLI entry: `uv run census-api` (`[project.scripts]`).
- Production release remains gated on Track 3 provenance completion.

Tests: `app_test_scripts/test_fastapi_app.py` (health, query, SSE, new_thread, resumed thread delta state).

Evidence (2026-07-18, post A4):

```bash
uv run ruff check src app_test_scripts
uv run pytest app_test_scripts/ -m "not integration" -q
```

Result: **334 passed**, 12 deselected (integration).
