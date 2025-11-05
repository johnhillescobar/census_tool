# Agent Output Format Specification

## Overview

This document specifies the expected output format for the CensusQueryAgent. All agent outputs must conform to a Pydantic-validated structure to ensure consistency, type safety, and reliable parsing.

## Structure

All agent outputs must conform to this structure:

```json
{
  "census_data": {
    "success": bool,
    "data": [[...headers...], [...row1...], [...row2...], ...],
    "variables": {"var_code": "label", ...}  // optional
  },
  "data_summary": "Brief description of what was retrieved",
  "reasoning_trace": "Agent's step-by-step reasoning",
  "answer_text": "Natural language answer to user's question",
  "charts_needed": [{"type": "bar|line", "title": "..."}],
  "tables_needed": [{"format": "csv|excel", "title": "..."}],
  "footnotes": ["Source: ...", "Disclaimer: ...", ...]
}
```

## Field Specifications

### census_data (required)

Contains the actual Census data retrieved from the API.

**Type**: Object with required fields:
- `success` (bool): Whether the data fetch succeeded
- `data` (array of arrays): Census data in row format
  - First row: Column headers (e.g., `["NAME", "B01003_001E", "state"]`)
  - Subsequent rows: Data values (e.g., `["California", "39538223", "06"]`)
- `variables` (object, optional): Mapping of variable codes to labels
  - Example: `{"B01003_001E": "Total Population"}`

**Example**:
```json
{
  "success": true,
  "data": [
    ["NAME", "B01003_001E", "state"],
    ["California", "39538223", "06"],
    ["Texas", "29145505", "48"]
  ],
  "variables": {
    "B01003_001E": "Total Population"
  }
}
```

### data_summary (required)

**Type**: String

Brief description of what data was retrieved. Should include:
- Table code(s) used
- Geography level
- Number of records
- Time period (year)

**Example**: `"Retrieved B01003 (Total Population) for 50 states from 2023 ACS 5-Year estimates"`

### reasoning_trace (required)

**Type**: String

The agent's step-by-step reasoning process. Should document:
- Geography resolution steps
- Table search/validation
- API call construction
- Any issues encountered

**Example**: `"Resolved California to FIPS 06, validated B01003 supports state geography, queried 2023 ACS5 dataset"`

### answer_text (required)

**Type**: String

Natural language answer to the user's question. This is the primary user-facing output.

**Guidelines**:
- Should be 1-3 sentences for simple queries
- Up to a paragraph for complex comparisons
- Must include actual numbers from census_data
- Format numbers with commas (e.g., "39,538,223")
- Be conversational but professional
- Can stand alone without charts/tables

**Example**: `"California has a population of 39,538,223 people according to 2023 ACS 5-Year estimates, making it the most populous state in the nation."`

### charts_needed (required, can be empty array)

**Type**: Array of objects

Specifies data visualizations to generate.

**Object structure**:
```json
{
  "type": "bar" | "line",
  "title": "Descriptive chart title"
}
```

**Usage**:
- `bar`: For comparisons across locations or categories
- `line`: For trends over time

**Example**:
```json
[
  {"type": "bar", "title": "Population by State (Top 10)"},
  {"type": "line", "title": "California Population Trend 2015-2023"}
]
```

### tables_needed (required, can be empty array)

**Type**: Array of objects

Specifies data exports to generate.

**Object structure**:
```json
{
  "format": "csv" | "excel" | "html",
  "filename": "optional_name",  // optional
  "title": "Descriptive table title"
}
```

**Example**:
```json
[
  {
    "format": "csv",
    "filename": "state_population_2023",
    "title": "State Population Data 2023"
  }
]
```

### footnotes (required, minimum 2)

**Type**: Array of strings

Source citations and disclaimers. Must include:

1. **Data source citation** (always required):
   - Example: `"Source: U.S. Census Bureau, 2023 American Community Survey 5-Year Estimates."`

2. **Statistical disclaimer** (always required):
   - Example: `"Margins of error not shown. For statistical significance, refer to Census Bureau documentation."`

3. **Table codes** (recommended):
   - Example: `"Census table(s) used: B01003 (Total Population)."`

4. **Methodology notes** (if relevant):
   - Example: `"Income values are adjusted for 2023 inflation using CPI-U."`

5. **General disclaimer** (recommended):
   - Example: `"This tool is for informational purposes only. Verify critical data at census.gov."`

**Example**:
```json
[
  "Source: U.S. Census Bureau, 2023 American Community Survey 5-Year Estimates.",
  "Margins of error not shown. For statistical significance, refer to Census Bureau documentation.",
  "Census table(s) used: B01003 (Total Population).",
  "This tool is for informational purposes only. Verify critical data at census.gov."
]
```

## Validation

### Pydantic Models

The output is validated using Pydantic models defined in `src/utils/agents/census_query_agent.py`:

```python
class CensusData(BaseModel):
    success: bool
    data: List[List[Any]]
    variables: Optional[Dict[str, str]] = None

class AgentOutput(BaseModel):
    census_data: CensusData
    data_summary: str
    reasoning_trace: str
    answer_text: str
    charts_needed: List[Dict[str, str]] = []
    tables_needed: List[Dict[str, str]] = []
    footnotes: List[str] = []
```

### Error Handling

If validation fails:
1. Pydantic will raise `ValidationError` with details
2. Parser falls back to empty structure:
   ```json
   {
     "census_data": {},
     "data_summary": "Parsing failed - see logs",
     "reasoning_trace": "Steps: N",
     "answer_text": "Agent execution completed but output parsing failed",
     "footnotes": []
   }
   ```

## Performance Considerations

### Large Payloads

The parser supports large payloads (1000+ rows) with optimized parsing:
- Uses state machine for JSON extraction (handles nested structures)
- Handles escaped quotes in strings
- Supports deeply nested arrays (tested with 67 counties × 100+ variables)

### Data Volume Optimization

**Best Practice**: Minimize data volume by specifying only needed variables.

❌ **Bad** (fetches 100+ variables):
```json
{
  "year": 2023,
  "dataset": "acs/acs5/cprofile",
  "variables": ["group(CP03)"],  // Gets ALL economic indicators
  "geo_for": {"county": "*"},
  "geo_in": {"state": "12"}
}
```

✅ **Good** (fetches only needed variables):
```json
{
  "year": 2023,
  "dataset": "acs/acs5/cprofile",
  "variables": ["NAME", "CP03_001E", "CP03_002E"],  // Only employment rate
  "geo_for": {"county": "*"},
  "geo_in": {"state": "12"}
}
```

### When to Use group()

Only use `group(table_code)` syntax when:
1. User explicitly asks for "complete profile" or "all variables"
2. You need 10+ variables from the same table
3. Working with small tables (<20 variables)

For targeted queries, always specify exact variables to minimize response size and parsing time.

## Multi-Year Time Series Queries

When users request data across multiple years, the agent must:

1. Make separate API calls for each year
2. Restructure data into time series format
3. Use custom column names like "Year" and descriptive measure names
4. Output with "line" chart type

Example output structure:
```json
{
  "census_data": {
    "success": true,
    "data": [
      ["Year", "Median Household Income (USD)"],
      ["2015", "53,889"],
      ["2016", "55,322"],
      ["2017", "57,652"]
    ]
  },
  "charts_needed": [{"type": "line", "title": "Income Trends 2015-2017"}]
}
```

The chart generation automatically adapts to these custom column names.

## Agent Prompt Format

The agent must output in this format:

```
Thought: I now know the final answer
Final Answer: {"census_data": {...}, "data_summary": "...", ...}
```

**Critical**: The entire JSON object must be on ONE line with NO line breaks inside it.

## Testing

### Unit Tests

See `test/test_census_query_agent.py` for parsing tests:
- Direct JSON parsing
- Final Answer prefix extraction
- Large nested structures
- Escaped quotes
- Invalid structures

### Integration Tests

See `test/test_integration_agent_api.py` for end-to-end tests:
- Real Census API calls
- Multi-county queries
- Large responses (Texas with 254 counties)
- Chart and table generation

## Common Issues

### Issue 1: Parsing Fails on Large Responses

**Symptom**: "Agent execution completed but output parsing failed"

**Solution**: Agent is likely using `group()` syntax and fetching 100+ variables. Update query to specify only needed variables.

### Issue 2: Missing Required Fields

**Symptom**: Pydantic validation error

**Solution**: Ensure all required fields are present in agent output:
- census_data.success
- census_data.data
- data_summary
- reasoning_trace
- answer_text

### Issue 3: Escaped Quotes in Data

**Symptom**: JSON parsing fails with quote errors

**Solution**: Parser handles escaped quotes correctly. Ensure agent outputs properly escaped JSON.

## Examples

### Simple Query (Single State)

```json
{
  "census_data": {
    "success": true,
    "data": [
      ["NAME", "B01003_001E", "state"],
      ["California", "39538223", "06"]
    ],
    "variables": {
      "B01003_001E": "Total Population"
    }
  },
  "data_summary": "Retrieved B01003 for California from 2023 ACS 5-Year data",
  "reasoning_trace": "Resolved CA to FIPS 06, validated B01003, queried ACS5",
  "answer_text": "California has a population of 39,538,223 people (2023 ACS 5-Year estimates).",
  "charts_needed": [{"type": "bar", "title": "California Population"}],
  "tables_needed": [],
  "footnotes": [
    "Source: U.S. Census Bureau, 2023 American Community Survey 5-Year Estimates.",
    "Margins of error not shown. For statistical significance, refer to Census Bureau documentation.",
    "Census table(s) used: B01003."
  ]
}
```

### Complex Query (Multi-County Comparison)

```json
{
  "census_data": {
    "success": true,
    "data": [
      ["NAME", "B01003_001E", "state", "county"],
      ["Los Angeles County, California", "9848406", "06", "037"],
      ["Cook County, Illinois", "5265605", "17", "031"],
      ["Harris County, Texas", "4731145", "48", "201"]
    ]
  },
  "data_summary": "Retrieved B01003 for top 3 counties by population, 2023 ACS 5-Year",
  "reasoning_trace": "Enumerated all US counties, queried B01003, sorted by population",
  "answer_text": "The three most populous counties are Los Angeles County (9.8M), Cook County (5.3M), and Harris County (4.7M) according to 2023 ACS estimates.",
  "charts_needed": [{"type": "bar", "title": "Top 3 Counties by Population"}],
  "tables_needed": [{"format": "csv", "title": "County Population Data"}],
  "footnotes": [
    "Source: U.S. Census Bureau, 2023 American Community Survey 5-Year Estimates.",
    "Margins of error not shown. For statistical significance, refer to Census Bureau documentation.",
    "Census table(s) used: B01003 (Total Population).",
    "This tool is for informational purposes only. Verify critical data at census.gov."
  ]
}
```

## Version History

- **v1.0** (2025-11-01): Initial specification with Pydantic validation and optimized parsing


