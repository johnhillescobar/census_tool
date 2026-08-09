# CENSUS-21 reframe — table choice, then geography

> **Architecture banner (2026-08-08):** This ticket fixes **interim table-resume plumbing inside the legacy planner-first graph** (`geography_node` → halt → `geography_resume`). It is **not** the target architecture. End state: agent owns retrieval, table/geo selection, API composition, and multi-call execution — see [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md). Do not treat CENSUS-21 as proof that planner-first clarify/skip is acceptable long term.

**Status:** Replaces planner allowlist / auto-B01001 approach (2026-08-08).

**Parent:** [CENSUS-20](https://johnhillescobar.atlassian.net/browse/CENSUS-20) · **Blocks:** [CENSUS-22](https://johnhillescobar.atlassian.net/browse/CENSUS-22) (multiturn geography resume)

---

## Context (updated)

Golden row 3: *"Show total population for all California counties in 2023."*

**Live repro (2026-08-08):** `TABLE_AMBIGUOUS`, `requested_slot=table`, zero API calls. Geography retrieval never runs because `geography_node` finalizes table selection before geography.

July tier3 label `geography_blocked` is **stale** for this repro.

**Architecture principle:** Deterministic layers **harness** the agent — they do not pre-answer “which population table” via code allowlists (`B01001`/`B01003`). When Chroma returns multiple grounded table candidates, **user or agent** chooses; geography proceeds **after** table is locked.

**Do not use:** retired planner allowlist patterns (e.g. hard-coded B01001/B01003 table-code preference in the pre-agent selector). Those approaches were rejected as deterministic policy, not harnessing.

---

## How table clarification works today

### Turn 1 — `geography_node`

1. Analyze question → retrieve tables from Chroma.
2. `select_grounded_plan(table_evidence)` — if not `selected` → `_clarification(..., requested_slot="table")`.
3. Pending state saved on `WorkflowPlan`:
   - `pending_geography_clarification` (`original_query`, `trace_id`, `options` with `table_0`…, `requested_slot="table"`)
   - `retrieval_evidence` (table hit only — **no geography evidence yet**)
   - `requires_clarification=True`
4. Graph routes to `output` (not agent). Agent skips when `requires_clarification` (`agent_reasoning_node`).

**What works:** Table-slot copy/ids ([CENSUS-24](https://johnhillescobar.atlassian.net/browse/CENSUS-24)), grounded candidate IDs, trace preservation.

### Turn 2 — `geography_resume_node`

1. `memory_load` sees pending → routes to `geography_resume` (skips `temporal`/`geography`).
2. `resume_geography_clarification(plan, user_message)` validates option against preserved evidence.

**What is broken for table slot:** `_selection_for_option` requires **both** `table_id` and `hierarchy_id` (`geography_clarification_resume.py`). After table-only pending, hierarchy evidence does not exist → resume returns *"That option does not complete a compatible geography selection"* and never runs geography retrieval.

**Existing resume tests** cover **area/hierarchy** ambiguity only (`test_phase5_geography_clarification.py`, `test_phase6_clarification_multiturn.py`). **No test** for table-slot resume → geography continuation.

---

## Why this matters

Row 3 is blocked at the **correct** harness point (table ambiguity) but the **resume path cannot complete planning**. Treating ambiguity as failure, or auto-forcing B01001 in the planner, bypasses population-category reasoning and will not generalize to other population questions (race, housing, tenure, etc.).

---

## Options for the real fix

1. **Table resume continues planning (this ticket)** — On `requested_slot=table` resume: lock selected table, run geography retrieval + selection + validation (same rules as `geography_node` tail), then clear pending or clarify on geography slot. **Preferred.**
2. **Agent selects table before geography (follow-up)** — New planning step: pass grounded table candidates to agent; agent emits `table_id` from evidence; then geography runs. Defer unless user/agent NL selection on turn 1 is required.
3. **Planner code allowlist B01001/B01003** — **Rejected** — deterministic policy, not harnessing.

---

## Tasks

1. **Revert** uncommitted planner allowlist / population-code preference (keep analyzer search-language improvements only if they improve retrieval without forcing codes).
2. **Implement table-slot resume continuation** in `geography_clarification_resume.py` and/or `geography_resume_node`:
   - Branch on `pending.requested_slot == "table"`.
   - After valid table option: append geography retrieval (dataset/year from selected table), run grounded selection for geography, validate plan.
   - Do not require hierarchy/area in `_selection_for_option` when completing table slot only.
3. **Routing:** On table resume partial success (geography still ambiguous), keep pending with `requested_slot` geography/hierarchy/area; route to `output`. On full resolve, route to `benchmark` → … → `agent`.
4. **Row 3 acceptance:** Two-turn offline test — turn 1 `TABLE_AMBIGUOUS` + `table_*`; turn 2 `table_0` (or label match) → `county:*`, `state:06`, reaches agent path (or grounded plan valid). Optional: single-turn if Chroma unambiguous without allowlist.
5. **Tests:** Add table-slot resume tests; **remove** assertions that geography_node must auto-select B01001 on turn 1 when Chroma is ambiguous.
6. Update `fix_pr_backlog_plan.md` P0 section (modules + two-turn success for row 3).

---

## Acceptance criteria (redefined)

| AC | Criterion |
|----|-----------|
| **AC1** | Row 3 turn 1: grounded `TABLE_AMBIGUOUS` with `table_*` options **or** single-turn resolve — **not** unjustified `geography_blocked` / zero evidence |
| **AC2** | Row 3 turn 2: table selection → geography resolves `county:*` + `state:06` from Chroma evidence (no invented IDs) |
| **AC3** | No planner population table-code allowlist; fail-closed negatives N1–N4 still pass |
| **AC4** | Offline CI: new table-resume tests + Jira §5 block; full `pytest -m "not integration"` |
| **AC5** | Tier 3 credentialed smoke (S1/S2): documents pass or agent-layer gap — not merge blocker |

---

## Test matrix (redefined)

### Primary (new)

| Test | File | Assert |
|------|------|--------|
| Table pending shape | `test_table_clarification_slot.py` | Row 3 → `requested_slot=table`, `table_*`, table copy |
| **Table resume → geography** | `test_phase5_geography_clarification.py` or new `test_table_clarification_resume.py` | After `TABLE_AMBIGUOUS` pending, `table_0` → resolved geo `county:*`/`state:06` |
| **Two-turn row 3** | `test_golden_url_offline_regressions.py` | Simulate turn 1 clarify + turn 2 resume with Chroma-shaped fake |

### Keep (regression)

- `test_phase5_*` area resume, cancel, tamper reject
- `test_phase6_clarification_multiturn.py` geography area cases
- `test_phase6_golden_grounded_replay.py` row_3 URL/geo contract
- Fail-closed N1–N4

### Remove / demote

- `selected_table.table_code == B01001` at geography_node when pending was table ambiguous on turn 1
- Planner unit tests that assert `_CANONICAL_POPULATION_TABLE_CODES` or hard-coded population table preference
- Chroma-shaped fake that expects auto B01001 without user turn

### PR verification block

```bash
uv run pytest app_test_scripts/test_golden_url_offline_regressions.py \
  app_test_scripts/test_table_clarification_slot.py \
  app_test_scripts/test_phase5_geography_clarification.py \
  app_test_scripts/test_phase4_grounded_graph_and_guards.py \
  app_test_scripts/test_phase6_golden_grounded_replay.py -k row_3 \
  -m "not integration" -q
```

---

## Out of scope (this ticket)

- Agent-initiated table pick on turn 1 (separate follow-up)
- CENSUS-22 `"all of them"` geography enumeration (depends on turn-1 pending from this ticket)
- Index rebuild / Chroma alias tuning (optional enhancement)
- Tier 3 full re-collection (CENSUS-25)
