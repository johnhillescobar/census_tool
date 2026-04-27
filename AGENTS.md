# Census Tool — Agent Conventions

This file is read by Cursor at the start of every session. It defines the
stack, layout, and non-negotiable rules. It is the SLIM **L**ayout leg.
For goals, features, and boundaries see [SPEC.md](SPEC.md).

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

## Active migration track

Track 2 — Deterministic Planning Layer.

- Plan:
  [.cursor/plans/v2-track2-deterministic-planning.plan.md](.cursor/plans/v2-track2-deterministic-planning.plan.md)
- Sub-plan (still to be folded back in):
  `~/.cursor/plans/strict_census_artifacts_*.plan.md`
- Skill:
  [.cursor/skills/census-v2-tech-lead/SKILL.md](.cursor/skills/census-v2-tech-lead/SKILL.md)
- Latest audit:
  [migration_evidence/track2_progress_20260426/](migration_evidence/track2_progress_20260426/)

## Drift policy

- Run `/drift-audit` every **14 days during an active migration track**;
  every **30 days** once Track 4 (runtime modernization) exits.
- New regression patterns must be proposed to the user before adding to
  the catalog (see
  [.cursor/skills/drift-audit/SKILL.md](.cursor/skills/drift-audit/SKILL.md)
  step 5).
- Last run: 2026-04-26 →
  [migration_evidence/track2_progress_20260426/](migration_evidence/track2_progress_20260426/)
