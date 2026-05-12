# Agent Output Format Specification

## Overview
This document specifies the strict agent-emitted payload expected by `CensusQueryAgent` at the reasoning/output boundary.

Important scope note:
- This document describes the payload emitted by the agent before workflow storage.
- It does not redefine downstream render/export adapters.
- The payload is now aligned to the strict contract validated by `AgentSolveResult` and `StrictCensusApiResponse`.

## Canonical Shape
All agent outputs must conform to this structure:

```json
{
  "census_data": {
    "success": true,
    "request": {
      "year": 2023,
      "dataset": "acs/acs5",
      "variables": ["NAME", "B01003_001E"],
      "geo_for": {"county": "037"},
      "geo_in": {"state": "06"},
      "geo_in_chained": []
    },
    "headers": ["NAME", "B01003_001E"],
    "records": [
      {
        "values": {
          "NAME": "Los Angeles County, California",
          "B01003_001E": "9,848,406"
        }
      }
    ],
    "row_count": 1,
    "error": null,
    "error_message": null
  },
  "data_summary": "Brief description of what was retrieved",
  "reasoning_trace": "Agent's step-by-step reasoning",
  "answer_text": "Natural language answer to user's question",
  "charts_needed": [{"type": "bar|line", "title": "..."}],
  "tables_needed": [{"format": "csv|excel|html", "title": "..."}],
  "footnotes": ["Source: ...", "Disclaimer: ...", "..."]
}
```

## Non-Negotiable Rules
- `census_data` must use the strict `StrictCensusApiResponse` shape.
- Do not emit legacy `census_data.data = [[...], [...]]` table blobs.
- `charts_needed` must match `FinalChartSpec`.
- `tables_needed` must match `FinalTableSpec`.
- The entire `Final Answer` JSON must be on one line.
- If validation fails, the parser treats the payload as invalid and falls back to a typed failure result.

## Field Specifications

### `census_data`
Required when the agent has a Census result to report. The structure must match `StrictCensusApiResponse`.

Required fields:
- `success`
- `request`
- `headers`
- `records`
- `row_count`
- `error`
- `error_message`

Success-path rules:
- `request` must be present
- `headers` must be non-empty
- `records` must contain row objects with `values`
- `row_count` must equal `len(records)`
- `error` and `error_message` must be `null`

Failure-path rules:
- `error` must be present
- `headers` must be empty
- `records` must be empty
- `row_count` must be `0`

### `data_summary`
String summary of what was retrieved. Include table code(s), geography, number of records, and year when relevant.

### `reasoning_trace`
String summary of the agent's reasoning path: geography resolution, validation, query construction, and issues encountered.

### `answer_text`
Primary user-facing answer.

Rules:
- 1-3 sentences for simple queries, up to a paragraph for complex ones
- include actual numbers from `census_data`
- format numbers with commas
- conversational but professional

### `charts_needed`
Array of chart specs using this shape:

```json
{
  "type": "bar" | "line",
  "title": "Descriptive chart title"
}
```

### `tables_needed`
Array of table specs using this shape:

```json
{
  "format": "csv" | "excel" | "html",
  "filename": "optional_name",
  "title": "Descriptive table title"
}
```

### `footnotes`
Array of strings. Include at minimum:
- source citation
- statistical disclaimer

Recommended additions:
- table codes used
- methodology note when relevant
- general disclaimer

## Validation
The emitted payload is validated against:

```python
class AgentSolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_data: StrictCensusApiResponse = Field(...)
    variable_labels: VariableLabels = Field(default_factory=VariableLabels)
    data_summary: str = Field(...)
    reasoning_trace: str = Field(...)
    answer_text: str = Field(...)
    charts_needed: list[FinalChartSpec] = Field(default_factory=list)
    tables_needed: list[FinalTableSpec] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
```

The active validation path lives in:
- `src/domain/agent_output_contract.py`
- `src/domain/census_tool_contract.py`
- `src/agents/census_query_agent.py`

## Error Handling
If validation fails:
1. The parser rejects the emitted payload.
2. The agent falls back to a typed failure `AgentSolveResult`.
3. The fallback **never** uses JSON `null` for `census_data`; absence of a Census table is expressed as `success: false` with `error: "NO_STRICT_CENSUS_PAYLOAD"` per `StrictCensusApiResponse`.

Typical parse-fallback shape:

```json
{
  "census_data": {
    "success": false,
    "request": null,
    "headers": [],
    "records": [],
    "row_count": 0,
    "error": "NO_STRICT_CENSUS_PAYLOAD",
    "error_message": null
  },
  "data_summary": "Parsing failed - see logs",
  "reasoning_trace": "Steps: N",
  "answer_text": "Agent execution completed but output parsing failed",
  "charts_needed": [],
  "tables_needed": [],
  "footnotes": []
}
```

## Multi-Year Time Series Queries
When users request data across multiple years, the agent must:
1. make one `strict_census_api_call` per year
2. aggregate the final response into strict `headers` + `records`
3. use a `line` chart in `charts_needed`

Example `census_data` for a time series:

```json
{
  "success": true,
  "request": {
    "year": 2023,
    "dataset": "acs/acs5/subject",
    "variables": ["Year", "Median Household Income (USD)"],
    "geo_for": {"us": "1"},
    "geo_in": null,
    "geo_in_chained": []
  },
  "headers": ["Year", "Median Household Income (USD)"],
  "records": [
    {"values": {"Year": "2015", "Median Household Income (USD)": "53,889"}},
    {"values": {"Year": "2016", "Median Household Income (USD)": "55,322"}},
    {"values": {"Year": "2017", "Median Household Income (USD)": "57,652"}}
  ],
  "row_count": 3,
  "error": null,
  "error_message": null
}
```

## Common Issues

### Missing strict fields
Symptom: validation error or parser fallback.

Required strict fields to check:
- `census_data.success`
- `census_data.request`
- `census_data.headers`
- `census_data.records`
- `census_data.row_count`
- `data_summary`
- `reasoning_trace`
- `answer_text`

### Legacy table blob emitted
Symptom: strict parser rejects payload.

Wrong:

```json
{
  "census_data": {
    "success": true,
    "data": [["NAME"], ["California"]]
  }
}
```

Correct:

```json
{
  "census_data": {
    "success": true,
    "request": {
      "year": 2023,
      "dataset": "acs/acs5",
      "variables": ["NAME"],
      "geo_for": {"state": "06"},
      "geo_in": null,
      "geo_in_chained": []
    },
    "headers": ["NAME"],
    "records": [{"values": {"NAME": "California"}}],
    "row_count": 1,
    "error": null,
    "error_message": null
  }
}
```

## Testing
Focused strict parser coverage lives in:
- `app_test_scripts/test_census_query_agent.py`

That test file now enforces:
- strict direct JSON parsing
- strict `Final Answer:` extraction
- strict large-payload handling
- rejection of legacy `census_data.data` payloads


