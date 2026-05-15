# Census Tool — Agent Conventions

This file is read by Cursor at the start of every session. It defines the
stack, layout, and non-negotiable rules. It is the **bootstrap-SLIM** Layout
leg. For goals, features, and boundaries see [SPEC.md](SPEC.md). For the
unrelated refactor-SLIM skill see `.cursor/skills/slim/SKILL.md`.

## Stack

- Python 3.12+
- Package manager: **uv** (do not use pip/poetry)
- LangGraph (workflow orchestration)
- LangChain (agent tooling)
- Pydantic v2 (typed contracts)
- pytest (tests in `app_test_scripts/`)
- Streamlit (browser UI)
- ReportLab (PDF generation)
- Plotly + tabulate (rendering, edge-only)

## Layer order

Strict dependency direction: `domain` depends on nothing; `api` depends on
all layers below.

```text
domain → clients → services → agents → workflows → api
```

- `src/domain/` — pure typed contracts, no I/O, no logic
- `src/clients/` — external I/O wrappers (Census API, PDF, files)
- `src/services/` — business logic, deterministic math, adapters
- `src/agents/` — `CensusQueryAgent` (LangChain tool-loop)
- `src/workflows/` — LangGraph nodes; consume typed state, write typed state
- `src/api/` — display surfaces (CLI display, future FastAPI)
- `src/state/` — `CensusState` envelope (LangGraph reducer schema)
- `src/tools/` — LangChain tools registered on the agent
- `src/llm/` — LLM config + factory

## Top-level layout (outside `src/`)

Canonical code and docs at repo root and alongside `src/`:

- `app_test_scripts/` — pytest (`test_*.py`)
- `app_description/` — architecture deep-dive (`ARCHITECTURE.md`, geography summaries, migration notes)
- `docs/` — contributor-focused notes (contracts primer, track framework, common errors)
- `index/` — Chroma / catalog index builders (`build_index.py`, etc.)
- `migration_evidence/` — track baselines and drift snapshots
- `.cursor/plans/` — versioned migration plans
- `articles/`, `test_questions/` — notes and sample question sets
- `data/`, `chroma/`, `memory/`, `logs/` — runtime artifacts (often gitignored or machine-local)

Entrypoints: `app.py` (graph), `main.py` (CLI), `launcher.py` (menu), `streamlit_app.py` (browser). **Full tree**: see the **Project Structure** section in [README.md](README.md).

## Non-negotiable contract rules

From
[.cursor/skills/census-v2-tech-lead/SKILL.md](.cursor/skills/census-v2-tech-lead/SKILL.md):

1. Workflows never pass raw dicts. Use Pydantic models in
   `src/state/types.py`.
2. Agents never parse raw strings. Tool observations are the source of
   truth.
3. Tools never return unvalidated objects. Use `StrictCensusApiResponse`
   etc.
4. Infrastructure never persists unversioned models.

Violations are catalogued in
[.cursor/skills/drift-audit/references/known-regressions.md](.cursor/skills/drift-audit/references/known-regressions.md)
(R1-R13).

## Working mode (this is a learning project)

The repo owner is **learning to code**, not outsourcing implementation.
Per [.cursor/rules/general.mdc](.cursor/rules/general.mdc), the agent
operates in one of three modes per turn.

### Mode A — Socratic (default)

- Ask clarifying questions
- Point to relevant files with `file:line` references
- Show options + trade-offs, not solutions
- The user writes the code; the agent does not propose code blocks

### Mode B — Show-in-chat (user is stuck)

Triggered when the user says they're stuck or asks the agent to
"show the code", "show in chat", "I'm stuck", or equivalent.
The agent then:

- Shows the proposed code **in a chat code block only** (not written to
  any file)
- The user reads it and **retypes it manually** into the actual file —
  this is the learning step, not a copy-paste step
- After the user reports the change is in place, the agent **reviews**
  the actual file (Read tool), grades it 🔴/🟡/🟢 against the rule
  being applied, and gives feedback for future reference (what to
  remember, what to watch for)

### Mode C — Direct edit (rare, requires explicit permission)

Triggered only when the user says "write the code", "edit the file",
"go ahead and write it", or equivalent. The agent edits files directly.
This mode is the exception, not the default.

### What the agent CAN write without explicit code-writing permission

These are governance artifacts, not implementation code:

- Drift audit reports under `migration_evidence/`
- Catalog updates under `.cursor/skills/drift-audit/references/`
- Track plans under `.cursor/plans/`
- Doc files at the repo root (`SPEC.md`, `AGENTS.md`, etc.) when drafted
  in chat first and approved

### Goal

The user should be able to plan, organize, and execute software work
*without* AI tools, and direct AI tools effectively when they are
available.

## SLIM disciplines — when to use which

This repo has two unrelated disciplines that share the acronym SLIM:

- **Use bootstrap-SLIM** when starting something new or grounding the
  session: define spec, then layout, then implement, then monitor.
  `SPEC.md` and `AGENTS.md` are the persistent artifacts; this is the
  organizing framing for the whole project.
- **Use refactor-SLIM** (the skill at
  [.cursor/skills/slim/SKILL.md](.cursor/skills/slim/SKILL.md)) when
  modifying code you don't fully understand without breaking it: pick a
  seam, write learning tests, extract incrementally, mock the seam. The
  skill is invoked per-task, not persisted. Especially relevant for the
  current Track 2 typed-state migration work (R3 cluster, N4 streamlit
  dead-schema, workflow↔agent boundary cleanup).

The two disciplines compose with [working modes](#working-mode-this-is-a-learning-project):
SLIM tells the agent *what* to do per turn, working modes tell the agent
*how* to communicate per turn.

## Active migration track

**Track 2 — Deterministic Planning Layer** (`2A`–`2D`) plus **Track 2E (raw JSON /
`CensusState` channel closure)** is **closed**.

- **Track 2E (final strict-state JSON gate):** [migration_evidence/track2_progress_20260511/track2e_raw_dict_closeout.md](migration_evidence/track2_progress_20260511/track2e_raw_dict_closeout.md)
  — drift ratchet: [`scripts/track2_raw_dict_audit.py`](scripts/track2_raw_dict_audit.py) /
  [`scripts/track2_raw_dict_baseline.txt`](scripts/track2_raw_dict_baseline.txt)
- **Track 2A**: [migration_evidence/track2_progress_20260504/track2a_closeout.md](migration_evidence/track2_progress_20260504/track2a_closeout.md)
- **Track 2B**: [migration_evidence/track2_progress_20260511/track2b_closeout.md](migration_evidence/track2_progress_20260511/track2b_closeout.md)
- **Track 2C**: [migration_evidence/track2_progress_20260511/track2c_closeout.md](migration_evidence/track2_progress_20260511/track2c_closeout.md)
- **Track 2D** (tooling/governance gate): [migration_evidence/track2_progress_20260511/track2d_closeout.md](migration_evidence/track2_progress_20260511/track2d_closeout.md)

**Next:** **Track 3 — Provenance Enforcement** per
[.cursor/plans/v2-track3-provenance-enforcement.plan.md](.cursor/plans/v2-track3-provenance-enforcement.plan.md).

- Plan:
  [.cursor/plans/v2-track2-deterministic-planning.plan.md](.cursor/plans/v2-track2-deterministic-planning.plan.md)
- Sub-plan (still to be folded back in):
  `~/.cursor/plans/strict_census_artifacts_*.plan.md`
  — **`derive-tabular-view`** (shared adapter + dataframe + CSV/Parquet export helpers) is **completed** in that YAML; **`migrate-consumers`**, **`tighten-tests`**, **`decide-census-data-required-vs-optional`** remain open there.
- Skill:
  [.cursor/skills/census-v2-tech-lead/SKILL.md](.cursor/skills/census-v2-tech-lead/SKILL.md)
- Latest evidence refresh:
  [migration_evidence/track2_progress_20260511/](migration_evidence/track2_progress_20260511/)
  (includes `track2e_raw_dict_closeout.md`).

## Drift policy

- Run `/drift-audit` every **14 days during an active migration track**;
  every **30 days** once Track 4 (runtime modernization) exits.
- New regression patterns must be proposed to the user before adding to
  the catalog (see
  [.cursor/skills/drift-audit/SKILL.md](.cursor/skills/drift-audit/SKILL.md)
  step 5).
- Last evidence refresh: 2026-05-12 →
  [migration_evidence/track2_progress_20260511/](migration_evidence/track2_progress_20260511/)
  (includes `track2d_closeout.md`).
