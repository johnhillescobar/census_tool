# CENSUS-39 parallel worktrees and phase ordering

Epic **CENSUS-39** implements agent-first grounded planning per [agent-first-grounded-planning.md](./agent-first-grounded-planning.md) (Migration phases section).

**Base branch:** `main` @ `b8285fb` (after PR #51 merge).

## Parallel vs sequential matrix

| Ticket | Phase | Depends on | Parallel with (same wave) | Rationale |
|--------|-------|------------|---------------------------|-----------|
| **CENSUS-40** | 1 — Agent planning turn after temporal | Doc alignment (done) | **CENSUS-45** | Reorders graph / agent loop (`src/workflows/*`, `census_query_agent.py`). Foundation for phases 2–4. |
| **CENSUS-45** | 5 — Chroma index metadata | None (index builders) | **CENSUS-40** | Touches `index/build_index_table.py` and catalog metadata; no production graph authority change. Low merge conflict vs graph work if merged early. |
| **CENSUS-41** | 2 — Validator harness node | **CENSUS-40** (agent plan turn exists) | — | Replaces `geography_node` authority; same workflow files as 40. **Sequential after 40.** |
| **CENSUS-44** | 3 — Agent-driven clarification | **CENSUS-40**; practically **CENSUS-41** | — | Merges resume/clarify into agent checkpoint flow; overlaps `geography_clarification_resume`, graph routing. **After 41 recommended.** |
| **CENSUS-42** | 4 — Retire planner select in production | **CENSUS-40–44** | — | Demotes `select_grounded_plan`; must run when agent+validator+clarify paths own decisions. **Last graph phase.** |
| **CENSUS-43** | Follow-up: turn-1 table selection | **CENSUS-40** | — | Extends phase 1 behavior; same agent/graph surface as 40. **After 40 merges** (or stacked PR). |

### Waves (recommended)

| Wave | Tickets | Notes |
|------|---------|--------|
| **Wave 1** | CENSUS-40, CENSUS-45 | Only pair safe to develop in parallel from `main`. |
| **Wave 2** | CENSUS-41 | Merge CENSUS-40 first (CENSUS-45 can land anytime in wave 1–2). |
| **Wave 3** | CENSUS-44 | Agent clarification on top of validator harness. |
| **Wave 4** | CENSUS-42 | Remove score-rank planner from production path. |
| **Wave 5** | CENSUS-43 | Follow-up polish on turn-1 table selection. |

**Strict sequence (graph-critical path):** 40 → 41 → 44 → 42. **CENSUS-45** is off the critical path. **CENSUS-43** branches from 40 outcomes.

## Git worktrees (Wave 1 only)

Worktrees live under repo root `.worktree/` (not part of the main index; each checkout is its own working tree).

| Path | Branch | Ticket |
|------|--------|--------|
| `.worktree/census-40-agent-planning-turn` | `feat/census-40-agent-planning-turn` | CENSUS-40 |
| `.worktree/census-45-chroma-metadata` | `feat/census-45-chroma-metadata` | CENSUS-45 |

Sequential tickets (**41, 44, 42, 43**) have **no** worktrees here to avoid heavy merge conflicts on shared workflow files. Create after upstream phases merge:

```powershell
cd c:\Users\johnh\Dropbox\Python\census_tool
git worktree add .worktree/census-41-validator-harness -b feat/census-41-validator-harness main
git worktree add .worktree/census-44-agent-clarification -b feat/census-44-agent-clarification main
git worktree add .worktree/census-42-retire-planner-select -b feat/census-42-retire-planner-select main
git worktree add .worktree/census-43-turn1-table-selection -b feat/census-43-turn1-table-selection main
```

(Re-run from updated `main` after each wave merges.)

## Recreate Wave 1 worktrees

From repo root on `main`:

```powershell
git fetch origin
git checkout main
git pull origin main

git worktree add .worktree/census-40-agent-planning-turn -b feat/census-40-agent-planning-turn main
git worktree add .worktree/census-45-chroma-metadata -b feat/census-45-chroma-metadata main
```

If branches already exist:

```powershell
git worktree add .worktree/census-40-agent-planning-turn feat/census-40-agent-planning-turn
git worktree add .worktree/census-45-chroma-metadata feat/census-45-chroma-metadata
```

## Useful commands

```powershell
git worktree list
git worktree remove .worktree/census-40-agent-planning-turn   # after branch merged/abandoned
```

Open in editor: open the `.worktree/<name>` folder as a separate workspace or use Cursor multi-root.

## `.gitignore`

Do **not** add `.worktree/` to `.gitignore` unless you want to hide local worktree folders from untracked listings; worktree checkouts are never committed to `main`. This doc is the canonical layout reference in-repo.
