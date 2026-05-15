# Track 2E — Raw Dict / JSON Channel Closure

**Date:** 2026-05-12  
**Status:** **Closed** for the scoped raw–JSON–channel goal (see §Closure Standard below).

## Closure Standard (Track 2E)

Track 2E closes when the **primary `CensusState` JSON-ish channels** (`messages`,
`intent`, `geo`, `candidates`, `profile`, `history`, `cache_index`) are represented by
**Pydantic-validated envelopes** instead of unbounded `dict[str, Any]` / implicit
list-of-dict history rows, and LangGraph node outputs use a **typed patch**
(`CensusGraphPatch`) instead of ad-hoc `{str: ...}` construction for those fields.

This does **not** claim the entire repo is free of `dict[str, Any]` *text* —
compatibility layers for LangChain tools, Census client helpers, and telemetry
still surface `Any` ergonomics. Those are **explicitly ratcheted** via
`scripts/track2_raw_dict_audit.py` against `scripts/track2_raw_dict_baseline.txt`.

## What Landed

| Area | Change | Primary files |
| --- | --- | --- |
| Recursive JSON envelope | `JsonMap` + `ConversationMessage` helpers | `src/domain/strict_json.py` |
| `CensusState` | Typed channels + coerce-on-assignment + typed reducers where needed | `src/state/types.py` |
| LangGraph deltas | `CensusGraphPatch.as_langgraph_update()` keeps nested models as instances (no lossy `model_dump` for artifact patches) | `src/workflows/graph_patch.py` |
| Workflow nodes | Temporal / benchmark / comparison / metrics / agent / output / memory emit patches | `src/workflows/*.py` |
| Persistence | v2 profile + cache envelopes hydrate into `JsonMap` / `list[JsonMap]` | `src/domain/memory_persistence_contract.py`, `src/services/memory_utils.py` |
| Agent | `solve()` coerces mapping-like intents to `JsonMap` | `src/agents/census_query_agent.py` |
| Entrypoints | CLI + Streamlit seed typed `messages` + `WorkflowArtifactsState` | `main.py`, `streamlit_app.py` |
| Verification | `pytest` (non-integration) + expanded `mypy` file list + textual dict audit ratchet | `pyproject.toml`, `app_test_scripts/`, `scripts/` |

## Verification Evidence

- **Pytest:** `uv run pytest app_test_scripts/ -m "not integration and not slow"` → **228 passed** (2026-05-12 sweep in this workspace).
- **`mypy` gate:** `uv run mypy` (scoped files in `pyproject.toml`, now includes `strict_json`, `memory_persistence_contract`, `graph_patch`) → **Success: no issues found in 12 source files**.
- **Drift ratchet:**  
  `uv run python scripts/track2_raw_dict_audit.py --summary` → **100** unsuppressed textual hits, matching `scripts/track2_raw_dict_baseline.txt`.  
  Strict check:  
  `uv run python scripts/track2_raw_dict_audit.py --strict --max-hits 100 --summary` → exit **0**.

## Residual / Follow-Ups (not re-opening 2E scope)

- Reduce the **100** `dict[str, Any]` textual hits by tightening tool + client surfaces (Track 3+ / incremental PRs).
- Promote selected `JsonMap` bags (e.g., `intent`, `geo`) to **domain-shaped** models when/if the project needs stricter field enforcement than JSON validation.
- Integrations tests (`-m integration`) still require live credentials; they were **not** part of the automated sweep above.

## Statement

**Track 2E closed for its stated goal:** core `CensusState` JSON channels and graph
memory load/write paths are guarded by Pydantic envelopes + explicit LangGraph patch
typing, with observability via tests, `mypy` expansion, and the raw-dict textual
ratchet.
