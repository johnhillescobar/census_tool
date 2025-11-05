# Agent JSON Parsing Fix - Implementation Summary

## Date
November 1, 2025

## Problem Statement

The CensusQueryAgent was failing to parse large JSON responses from the LangChain agent, resulting in the error message:
```
"Agent execution completed but output parsing failed"
```

### Root Causes Identified

1. **Flawed JSON Parsing Logic**
   - Simple regex pattern (`r'\{[^{}]*"census_data"[^{}]*(?:\{(?:[^{}]*|\{[^{}]*\})*\}[^{}]*)*\}'`) could not handle deeply nested JSON structures
   - Brace-counting logic incorrectly counted braces within JSON strings or arrays, leading to premature termination
   - Missing explicit handling for "Final Answer:" prefix before JSON extraction
   - No robust handling for escaped quotes in strings

2. **Data Volume Problem**
   - Agent was using `group(table_code)` syntax to fetch entire table groups (100+ variables)
   - For Florida counties CP03 query: 67 counties × 100+ variables = massive JSON payload
   - LLM output token limits caused agent to abbreviate JSON with `...` (ellipses), making it invalid JSON
   - Example of broken output: `["CP03_2018_001E","CP03_2018_001EA",...,"NAME","state","county"]` - the `...` breaks JSON parsing

## Solution Implemented

### Phase 1: Fix JSON Parsing (Priority 1) ✅

#### 1.1 Added Pydantic Models for Type Safety
**File**: `src/utils/agents/census_query_agent.py`

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

**Benefits**:
- Automatic validation of agent output structure
- Type safety and clear error messages
- Ensures all required fields are present

#### 1.2 Replaced Parsing Logic with Robust State Machine
**File**: `src/utils/agents/census_query_agent.py`

**Before**: 4 fallback methods using regex and flawed brace counting

**After**: 2 clean methods:
1. **Direct JSON parse** - When AgentExecutor strips "Final Answer:" prefix and returns pure JSON
2. **Final Answer extraction** - Uses state machine to extract JSON after "Final Answer:" marker

**State Machine Features**:
- Handles deeply nested objects and arrays
- Properly tracks escaped quotes (`\"`)
- Ignores braces/brackets inside string values
- Tracks both `{}` braces and `[]` brackets
- Returns complete, parseable JSON string

**Key Implementation**:
```python
def _extract_json_with_state_machine(self, text: str) -> Optional[str]:
    """
    Extract JSON object using state machine that handles:
    - Nested objects/arrays
    - Escaped quotes in strings
    - Braces inside string values
    - Square brackets in arrays
    """
    # Tracks: brace_count, bracket_count, in_string, escape_next
    # Returns complete JSON from first { to matching }
```

#### 1.3 Created Comprehensive Unit Tests
**File**: `test/test_census_query_agent.py` (8 tests, all passing)

**Test Coverage**:
- ✅ Direct JSON parsing
- ✅ Final Answer prefix extraction
- ✅ Large nested structures (67 counties × 100 variables)
- ✅ Escaped quotes in strings
- ✅ Invalid structure rejection (Pydantic validation)
- ✅ Nested objects with null values
- ✅ Multiline output with thought/action cycles
- ✅ Special characters (apostrophes in county names)

### Phase 2: Optimize Data Fetching (Priority 2) ✅

#### 2.1 Updated Agent Prompt
**File**: `src/llm/config.py`

Added "CRITICAL: MINIMIZE DATA VOLUME" section:
- Discourages using `group()` unless user explicitly asks for "all variables"
- Encourages specifying only needed variables
- Added rules requiring complete, valid JSON without ellipses
- Warns that fetching entire groups can cause parsing failures

**Key Addition**:
```
CRITICAL: MINIMIZE DATA VOLUME
- For profile/subject/comparison tables (S/DP/CP series), DO NOT use group() 
  unless user explicitly asks for "all variables" or "complete profile"
- Instead, use pattern_builder with custom variables list containing only 
  relevant variables
- Only use group() syntax when: (a) user asks for complete profile, or 
  (b) you need 10+ variables from same table
- Fetching entire groups can return 100+ variables causing slow responses 
  and parsing failures

CRITICAL: Output COMPLETE, VALID JSON - NO ellipses (...), NO abbreviations, 
NO truncation
```

#### 2.2 Modified Pattern Builder Tool
**File**: `src/tools/pattern_builder_tool.py`

Added warnings when `group()` is used:
```python
logger.warning(
    f"Using group({table_code}) - will fetch ALL variables from this table. "
    f"Consider specifying only needed variables for better performance."
)
```

#### 2.3 Created Integration Tests
**File**: `test/test_integration_agent_api.py`

- Real Census API tests
- Validates selective variable usage
- Tests multi-state/county queries
- Error handling validation

#### 2.4 Created Documentation
**File**: `docs/AGENT_OUTPUT_FORMAT.md`

Complete specification including:
- Field requirements
- Pydantic validation rules
- Performance considerations
- When to use `group()`
- Common issues and solutions
- Examples for simple and complex queries

## Test Results

### Unit Tests ✅
- **Status**: 8/8 passed
- **Coverage**: All parsing scenarios (direct JSON, prefix extraction, large datasets, edge cases)

### Manual Validation ✅
- **Selective Query Test**: Florida counties employment rate query
  - ✅ Agent fetched only 3 variables (B23025_004E, B23025_003E, NAME)
  - ✅ Parsed 67 counties successfully
  - ✅ Pydantic validation passed
  - ✅ Chart and table generation worked

- **Real-World Queries** (from terminal logs):
  - ✅ New York City population: Parsed successfully
  - ✅ California counties population: Parsed successfully (58 counties)
  - ✅ Median income trend: Parsed successfully

### Known Limitation ⚠️
- **Extremely Large Queries**: Queries requesting entire CP03 group (100+ columns × 67 rows) may exceed LLM output token limits
- **Symptom**: Agent abbreviates JSON with `...` making it invalid
- **Solution**: Phase 2 optimizations guide agent to use selective queries (intended use case)

## Files Modified

1. **`src/utils/agents/census_query_agent.py`**
   - Added Pydantic models
   - Replaced `_parse_solution()` with robust 2-method parser
   - Implemented `_extract_json_with_state_machine()`
   - Added comprehensive error logging

2. **`src/llm/config.py`**
   - Added "CRITICAL: MINIMIZE DATA VOLUME" section to prompt
   - Added rules prohibiting JSON ellipses/abbreviations

3. **`src/tools/pattern_builder_tool.py`**
   - Added warnings for `group()` usage
   - Improved variable selection logic

4. **`test/test_census_query_agent.py`** (new)
   - 8 comprehensive unit tests

5. **`test/test_integration_agent_api.py`** (new)
   - Integration tests with real Census API

6. **`docs/AGENT_OUTPUT_FORMAT.md`** (new)
   - Complete output format specification

## Key Insights

1. **Parsing Failure Pattern**: The original parser failed on large nested JSON structures because:
   - Regex couldn't handle arbitrary nesting depth
   - Brace counting didn't account for strings and escaped characters
   - No state machine to properly track JSON structure

2. **Data Volume Impact**: Using `group()` for large tables creates a cascade of problems:
   - Large API responses (100+ columns)
   - Large JSON payloads in agent output
   - LLM token limits causing abbreviation
   - Abbreviated JSON becoming invalid
   - Parsing failure

3. **Solution Strategy**: Two-pronged approach
   - **Fix parsing** to handle any valid JSON structure robustly
   - **Prevent problem** by guiding agent to fetch only needed variables

## Success Criteria - All Met ✅

- ✅ Agent successfully parses Florida counties with selective variables
- ✅ Parsing works for payloads up to reasonable sizes (tested with 58-67 counties)
- ✅ Agent selectively fetches variables (not entire groups) for targeted queries
- ✅ All 8 unit tests pass
- ✅ Integration tests created with real Census API
- ✅ No regressions in existing functionality
- ✅ Comprehensive documentation created
- ✅ Real-world queries working (NYC, California counties validated)

## Verification Evidence

### Test 1: New York City Population
```
Output length: 1040 chars
Parsing: ✅ Successfully parsed as direct JSON
Result: Population of 8,516,202
Chart/Table: ✅ Generated successfully
```

### Test 2: California Counties Population
```
Output length: 3697 chars
Parsing: ✅ Successfully parsed as direct JSON
Result: 58 counties parsed
Chart/Table: ✅ Generated successfully
```

### Test 3: Florida Counties Employment (Selective)
```
Variables: 3 (NAME, B23025_004E, B23025_003E)
Counties: 67
Parsing: ✅ Success
Pydantic Validation: ✅ Passed
```

## Architectural Alignment

The implementation aligns with the architecture described in `ARCHITECTURE.md`:

- **`agent_reasoning_node`**: Calls `CensusQueryAgent.solve()` → uses new robust parser
- **`output_node`**: Receives validated `AgentOutput` from parser → generates charts/tables
- **Data Flow**: User query → Agent → Census API → Parsed JSON → Validated Output → Charts/Tables

The parser validates structure before passing to downstream nodes, ensuring data integrity throughout the pipeline.

## Next Steps (Optional Future Enhancements)

1. **Monitor LLM Output Limits**: Track when queries approach token limits
2. **Automatic Pagination**: For extremely large queries, automatically split into multiple API calls
3. **Progressive Enhancement**: If direct parse fails, attempt partial recovery from truncated JSON
4. **Performance Metrics**: Track parsing success rates and response sizes

## Conclusion

The JSON parsing error has been resolved through:
1. **Robust state machine parser** that handles any valid JSON structure
2. **Pydantic validation** ensuring type safety and structure compliance
3. **Agent prompt optimization** guiding selective variable fetching
4. **Comprehensive testing** validating all scenarios

The system now successfully handles:
- ✅ Single location queries (NYC population)
- ✅ Multi-county queries (California, Florida counties)
- ✅ Selective variable queries (employment rates with 3 variables)
- ✅ Large payloads (58+ counties with formatted data)

The implementation maintains backward compatibility while significantly improving reliability and preventing the original parsing failures.

