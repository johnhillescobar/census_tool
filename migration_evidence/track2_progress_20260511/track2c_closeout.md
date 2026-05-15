# Track 2C Closeout — Output, UI, And Persistence Hardening

**Closed:** 2026-05-11 (implementation pass).  
**Parent plan gate:** `.cursor/plans/v2-track2-deterministic-planning.plan.md` (Track 2C).

## Verification (evidence)

Focused subset (recommended in Track 2C plan + related modules), with `LANGCHAIN_TRACING_V2=false`:

```text
pytest app_test_scripts/test_displays.py \
  app_test_scripts/test_pdf_generation.py \
  app_test_scripts/test_conversation_history_adapters.py \
  app_test_scripts/test_memory.py \
  app_test_scripts/test_memory_utils.py \
  app_test_scripts/test_table_tool.py \
  app_test_scripts/test_output_title_formatting.py \
  app_test_scripts/test_multi_series_charts.py \
  app_test_scripts/test_track2c_output_render.py \
  app_test_scripts/test_memory_persistence_v2.py \
  app_test_scripts/test_chart_tool_render_typed.py -q
```

**Result:** 74 passed (local run).

Full `app_test_scripts/` sweep was started but exceeded the agent’s wait window; rerun locally if whole-suite signoff is required.

## Implemented (by theme)

### Render success/failure artifacts

- `RenderedArtifactSuccess` / `RenderedArtifactFailure` discriminated union in `src/domain/rendered_output_contract.py`.
- Alias `RenderedArtifact` → `RenderedArtifactSuccess` for existing success-only call sites.
- `FinalResponseState.generated_files`: `list` of union with read-time coercion for legacy JSON missing `status` (`src/state/types.py` validator).

### `output_node`

- Charts/tables with no tabular payload → typed `NO_TABULAR_DATA` failures per spec row.
- Render exceptions → typed `RENDER_EXCEPTION` failures (`src/workflows/output.py`).

### Chart/table tool shim quarantine

- `ChartTool.render` / `TableTool.render`: **only** accept `ChartToolInput` / `TableToolInput` (`TypeError` otherwise).
- Legacy `str|dict` coercion remains on `_run` / `_execute` paths only (`src/tools/chart_tool.py`, `src/tools/table_tool.py`).

### CLI / Streamlit

- CLI: `display_results(CensusState)` + adapter `census_state_from_graph_invoke` (`src/api/displays.py`); `main.py` invokes the adapter once.
- Streamlit: `process_question` → `CensusState` including error-bearing state; `display_streamlit_results` takes `CensusState | None`; session dict legacy results coerced via `_session_current_result_as_state`; render failures shown via `st.warning` (`streamlit_app.py`).

### PDF

- Consumes validated `PdfConversationEntry` → `PdfConversationResult` → `FinalResponseState` artifacts.
- Successful vs failed artifact branches in session story (`src/clients/pdf_generator.py`).

### Versioned persistence

- `UserMemoryFileV2` / `CacheIndexFileV2` with `schema_version: 2` (`src/domain/memory_persistence_contract.py`).
- Load: migrate legacy blobs to v2 + prune retention; writes always serialize v2 (`src/workflows/memory.py`, `src/services/memory_utils.py` `enforce_retention_policies`).

## Risks / follow-ups

- ReportLab streams may compress narrative text in PDF binaries; behavioral tests rely on ingest validation + PDF byte generation smoke rather than verbatim string extraction.
- `_session_current_result_as_state` still admits a legacy `dict` from older Streamlit session pickles for one-hop coercion; new sessions persist `CensusState` instances only via `process_question`.
