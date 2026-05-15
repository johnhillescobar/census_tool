# Track 2 Progress - 2026-05-11

> **Supersession (Track 2B / Track 2D):** Investigation `T2-20260511-1`
> (“structured `invoke` vs `_run` mismatch”) was **resolved** — tools aligned
> and canonical `tool.invoke({...})` tests added; see
> `migration_evidence/track2_progress_20260511/track2b_closeout.md` and governance
> `migration_evidence/track2_progress_20260511/track2d_tooling_governance.md`.

## Purpose

Record runtime evidence from the Streamlit/agent tool loop failure observed on
2026-05-11. This note does not supersede the 2026-05-04 Track 2A closeout. It
adds a narrower Track 2B/2D finding: planning-critical tools expose typed
schemas, but the public LangChain tool invocation path is not currently covered
by the focused tests.

Closeout update: the Track 2B portion of this finding is closed by
`migration_evidence/track2_progress_20260511/track2b_closeout.md`. Track 2D
closed 2026-05-12 (`track2d_closeout.md`) with explicit `mypy`/invoke policy.

## Triggering Failure

The Streamlit run failed while answering:

```text
Show me median income trends from 2015 to 2020
```

The terminal showed this sequence:

```text
Action: validate_geography_params
Action Input: {"dataset":"acs/acs5/subject","year":2015,"geo_for":{"us":"1"}}
Observation: {"is_valid":true,"repaired_for":{"us":"1"},"repaired_in":null,"warnings":[],"errors":[]}
ERROR:__main__:Error processing question: 3 validation errors for GeographyValidationRequest
dataset
  Input should be 'acs/acs5', 'acs/acs5/profile', 'acs/acs5/cprofile',
  'acs/acs5/spp', 'acs/acs5/subject', 'acs/acs1', 'acs/acs1/profile',
  'acs/acs1/cprofile', 'acs/acs1/spp' or 'acs/acs1/subject'
  [type=literal_error, input_value='{"dataset":"acs/acs5/sub...rnings":[],"errors":[]}', input_type=str]
year
  Field required
geo_for
  Field required
```

The important point: `acs/acs5/subject` is a valid dataset. The invalid value is
the whole JSON observation string being interpreted as the next request's
`dataset` field.

## What Was Checked

Files inspected:

- `src/tools/geography_validation_tool.py`
- `src/domain/planning_tool_contracts.py`
- `src/tools/variable_validation_tool.py`
- `src/tools/strict_census_api_tool.py`
- `src/agents/census_query_agent.py`
- `src/llm/config.py`
- `migration_evidence/track2_progress_20260426/drift_audit.md`
- `migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`
- `.cursor/plans/v2-track2-deterministic-planning.plan.md`

Searches performed:

- `GeographyValidationRequest`
- `validate_geography_params`
- `geo_for`
- `_run(`
- `AgentExecutor`
- `handle_parsing_errors`

## Commands Run

Targeted direct-tool tests:

```text
uv run pytest app_test_scripts/test_track2_contract_first.py::test_planning_tools_expose_strict_args_schema app_test_scripts/test_geography_expansion.py::test_geography_validation_tool_valid_params -q
```

Result:

```text
2 passed in 5.23s
```

Public LangChain invocation checks:

```text
uv run python -c "from src.tools.geography_validation_tool import GeographyValidationTool; tool=GeographyValidationTool(); payload={'dataset':'acs/acs5/subject','year':2015,'geo_for':{'us':'1'}}; print('invoke:', tool.invoke(payload)); print('run:', tool._run(payload))"
```

Result:

```text
TypeError: GeographyValidationTool._run() got an unexpected keyword argument 'dataset'
```

```text
uv run python -c "from src.tools.variable_validation_tool import VariableValidationTool; payload={'action':'validate_variables','dataset':'acs/acs5/subject','year':2015,'variables':['NAME','S1903_C03_001E']}; tool=VariableValidationTool(); print(tool.invoke(payload))"
```

Result:

```text
TypeError: VariableValidationTool._run() got an unexpected keyword argument 'action'
```

```text
uv run python -c "from src.tools.strict_census_api_tool import StrictCensusApiTool; payload={'year':2015,'dataset':'acs/acs5/subject','variables':['NAME','S1903_C03_001E'],'geo_for':{'us':'1'}}; tool=StrictCensusApiTool(); print(tool.invoke(payload))"
```

Result:

```text
TypeError: StrictCensusApiTool._run() got an unexpected keyword argument 'year'
```

## Finding T2-20260511-1 - Structured Tool Invocation Path Untested

Status: closed (resolved in Track 2B; governance policy finalized in Track 2D).

Severity: high

Track impact: Track 2B and Track 2D

Problem: planning-critical tools declare Pydantic `args_schema` models, but
their `_run()` implementations are shaped like single-input tools. Direct
`_run(payload)` tests pass, while public `tool.invoke(payload)` calls fail with
unexpected keyword arguments.

Evidence:

- `src/tools/geography_validation_tool.py` declares
  `args_schema = GeographyValidationRequest`, but `_run()` accepts one
  `tool_input` positional parameter.
- `src/tools/variable_validation_tool.py` declares
  `args_schema = VariableValidationRequest`, but `_run()` accepts one
  `tool_input` positional parameter.
- `src/tools/strict_census_api_tool.py` declares
  `args_schema = StrictCensusApiRequest`, but `_run()` accepts one
  `tool_input` positional parameter.
- Targeted tests pass because they call `_run(payload)` directly.
- `tool.invoke(payload)` fails for all three planning-critical tools checked.

Why this matters:

LangChain structured tools pass validated schema fields as keyword arguments to
the tool execution method. If the method only accepts `tool_input`, the runtime
path used by `AgentExecutor` can diverge from the test path.

## Finding T2-20260511-2 - ReAct Parser Recovery Contaminates Tool Inputs

Status: open

Severity: high

Track impact: Track 2B

Problem: the terminal shows repeated output parsing failures before the
geography schema failure. After parser recovery, the tool loop appears to
reinterpret a prior observation as a new tool input, placing a full JSON
observation string inside the `dataset` field.

Evidence:

- The terminal first reports `Could not parse LLM output`.
- `AgentExecutor` is configured with `handle_parsing_errors` in
  `src/agents/census_query_agent.py`.
- The next visible tool action uses valid JSON for `validate_geography_params`.
- The following validation error reports the full observation string as
  `dataset`.

This is not proven to be caused only by `handle_parsing_errors`; it is the
current best-supported interpretation from the observed log. A focused
reproduction test around parser recovery and `validate_geography_params` would
be needed before changing parser behavior.

## Relation To Earlier Evidence

This refines, but does not replace, the 2026-05-04 evidence refresh.

**Note (2026-05-12):** Governance items from this sprint are finalized in

[`track2d_closeout.md`](track2d_closeout.md).

Relevant prior finding:

- `migration_evidence/track2_progress_20260504/track2_evidence_refresh.md`
  says N3/R11 is improved but not closed: tool observation can override
  LLM-restated `census_data`, but source-of-truth behavior still needs
  tightening in `src/agents/census_query_agent.py`.

**At drafting (2026-05-11)** the incident suggested an additional hypothesis:

Today's evidence adds a separate runtime boundary issue:

- The tool invocation contract itself is not covered by the existing focused
  tests.
- The visible failure happens before the strict Census API authority replacement
  path can help.

## Track 2 Plan Impact (2026-05-11 narrative)

Historical snapshot preserved for forensic traceability. Final governance is in
[`track2d_tooling_governance.md`](track2d_tooling_governance.md).

- Track 2A remains closed.
- Track 2B is closed (`track2b_closeout.md`); planning-critical structured tools have public `invoke` coverage.
- Track 2D is **closed 2026-05-12** (`track2d_closeout.md`); verification policy (invoke vs `_run`, scoped `mypy`, freeze) is recorded.

The bullets below retained verbatim from the 2026-05-11 draft describing *then-open* remediation:

Original recommended updates list (mostly delivered in Track 2B/2D):

1. Add focused tests that call `tool.invoke({...})` for planning-critical tools.
2. Align structured `args_schema` tools with LangChain's keyword invocation
   contract, or intentionally convert them to single-input JSON tools.
3. Add a parser-recovery regression test that proves an observation from
   `validate_geography_params` cannot be reinterpreted as the next request's
   `dataset`.
4. Keep direct `_run(payload)` tests only as unit tests; do not treat them as
   runtime integration evidence.

## Current Classification

This memo remains a forensic incident write-up dated 2026-05-11. Runtime + governance remediation is summarized in **`track2b_closeout.md`** and **`track2d_closeout.md`**.

