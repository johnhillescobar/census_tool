# Fix Application Regression and Enable All 70 Test Questions

## Problem Analysis

**Regression identified** (from terminal logs line 309):

```
Error: x_column 'NAME' not found in data. Available columns: ['Year', 'Median Household Income (USD)']
```

**Root cause**: `src/nodes/output.py:get_chart_params()` has hardcoded fallback to "NAME" when column detection fails. The agent creates custom column names that don't match the hardcoded expectations.

**Multi-year gap**: Agent prompt doesn't instruct on handling time series queries (questions 51-70 in test_questions_new.csv require data from 2010-2023).

**144 configurations**: Census API has 3 datasets (acs1/acs5/acs5c) × 12 geography levels (us/state/county/place/tract/etc.) × 4 table categories (detail/subject/profile/comparison) = 144+ patterns that agent must handle.

---

## Phase 1: Fix Chart Generation Regression (CRITICAL - Day 1)

### 1.1 Fix `get_chart_params()` in `src/nodes/output.py`

**Problem**: Hardcoded fallback to "NAME" column (line 137) fails when agent uses custom column names.

**Solution**: Make column detection flexible and extract actual column names from agent's census_data.

**Changes to `src/nodes/output.py`**:

**Lines 16-141** - Replace `get_chart_params()` function:

```python
def get_chart_params(census_data: Dict[str, Any], chart_type: str) -> Dict[str, str]:
    """
    Dynamically determine chart parameters from actual data structure.
    Adapts to ANY column names the agent provides.
    """
    try:
        # Extract headers from data
        if "data" in census_data and isinstance(census_data["data"], list) and len(census_data["data"]) >= 2:
            headers = census_data["data"][0]
        else:
            raise ValueError("Invalid census_data format")
        
        if len(headers) < 2:
            raise ValueError("Need at least 2 columns for chart")
        
        # Identify column types by content inspection
        text_columns = []
        numeric_columns = []
        time_columns = []
        
        # Sample first data row to determine types
        sample_row = census_data["data"][1] if len(census_data["data"]) > 1 else []
        
        for i, header in enumerate(headers):
            if i >= len(sample_row):
                continue
            
            value = str(sample_row[i]).replace(',', '')
            header_upper = header.upper()
            
            # Check for time columns
            if any(keyword in header_upper for keyword in ["YEAR", "DATE", "TIME", "PERIOD"]):
                time_columns.append(header)
            # Check if numeric
            elif value.replace('.', '').replace('-', '').isdigit():
                numeric_columns.append(header)
            # Otherwise text
            else:
                text_columns.append(header)
        
        # Determine x_column (categorical or time axis)
        x_column = None
        if chart_type == "line" and time_columns:
            # Time series: use time column for x-axis
            x_column = time_columns[0]
        elif text_columns:
            # Use first text column for categorical x-axis
            x_column = text_columns[0]
        else:
            # Fallback: use first column
            x_column = headers[0]
        
        # Determine y_column (numeric data)
        y_column = None
        if numeric_columns:
            # Use first numeric column that isn't the x_column
            for col in numeric_columns:
                if col != x_column:
                    y_column = col
                    break
            # If all numeric columns are x_column, use first numeric anyway
            if not y_column:
                y_column = numeric_columns[0]
        else:
            # Fallback: use second column if available
            y_column = headers[1] if len(headers) > 1 else headers[0]
        
        # Generate title
        if chart_type == "bar":
            title = f"{y_column} by {x_column}"
        elif chart_type == "line":
            title = f"{y_column} Trend"
        else:
            title = "Census Data Visualization"
        
        return {"x_column": x_column, "y_column": y_column, "title": title}
        
    except Exception as e:
        logger.error(f"Error determining chart parameters: {e}")
        # SAFE fallback: use first two columns from actual data
        if "data" in census_data and len(census_data.get("data", [])) > 0:
            headers = census_data["data"][0]
            return {
                "x_column": headers[0] if headers else "Column1",
                "y_column": headers[1] if len(headers) > 1 else "Column2",
                "title": f"Census Data Visualization ({chart_type})"
            }
        # Ultimate fallback
        return {"x_column": "Location", "y_column": "Value", "title": "Chart"}
```

**Validation**: Lines 187-201 already validate columns exist - keep this logic.

---

## Phase 2: Enable Multi-Year Time Series Queries (CRITICAL - Day 2)

### 2.1 Update Agent Prompt in `src/llm/config.py`

**Location**: Lines 172-329 (AGENT_PROMPT_TEMPLATE)

**Insert after line 291** (after "CRITICAL: MINIMIZE DATA VOLUME" section):

```python
MULTI-YEAR TIME SERIES QUERIES:

For queries requesting data across multiple years (e.g., "2015 to 2020", "trends since 2010"):

1. IDENTIFY year range from user question
2. MAKE MULTIPLE census_api_call invocations - ONE PER YEAR:
                                                                                 - Example: For "2015 to 2020" → make 6 separate calls (2015, 2016, 2017, 2018, 2019, 2020)
                                                                                 - Use same dataset, variables, and geography for each year
   
3. AGGREGATE results into time series format:
                                                                                 - Restructure data with columns: ["Year", "Measure Name", "<other geography columns>"]
                                                                                 - Example output format:
     [["Year", "Median Household Income (USD)", "Geography"],
      ["2015", "53,889", "United States"],
      ["2016", "55,322", "United States"],
      ...]

4. CHARTS for time series:
                                                                                 - ALWAYS use "line" chart type for multi-year trends
                                                                                 - Set x_column to "Year"
                                                                                 - Set y_column to the measure name
   
5. ANSWER TEXT for time series:
                                                                                 - Describe overall trend: "increased by X%" or "decreased from Y to Z"
                                                                                 - Mention starting value, ending value, and notable changes
                                                                                 - Example: "Median household income increased from $53,889 in 2015 to $68,700 in 2020, representing a 27.5% growth."

6. ERROR HANDLING:
                                                                                 - If a year is unavailable, note it in answer_text
                                                                                 - Continue with available years
                                                                                 - Example: "Data available for 2015-2019 and 2021-2023 (2020 data unavailable)"

Example multi-year reasoning:
Thought: User wants trends from 2015 to 2020. I need to query each year separately.
Action: census_api_call
Action Input: {{"year": 2015, "dataset": "acs/acs5/subject", "variables": ["S1903_C03_001E"], "geo_for": {{"us": "1"}}}}
Observation: [...2015 data...]
Thought: Now query 2016
Action: census_api_call
Action Input: {{"year": 2016, "dataset": "acs/acs5/subject", "variables": ["S1903_C03_001E"], "geo_for": {{"us": "1"}}}}
Observation: [...2016 data...]
... (repeat for 2017, 2018, 2019, 2020)
Thought: I now have all years. Restructure into time series format.
Final Answer: {{"census_data": {{"success": true, "data": [["Year", "Median Household Income (USD)"], ["2015", "53,889"], ["2016", "55,322"], ...]}}...}}
```

### 2.2 Verify census_api_call supports all years

**File**: `src/tools/census_api_tool.py`

**Check**: Lines 55-68 - Confirm `year` parameter is properly extracted and passed to `fetch_census_data()`.

**Expected**: No changes needed - tool already supports any year parameter.

---

## Phase 3: Test and Validate All 70 Questions (Day 3-5)

### 3.1 Add Session Logging System

**New file**: `src/utils/session_logger.py`

```python
import os
import logging
from datetime import datetime
from pathlib import Path

class SessionLogger:
    """
    Captures all logs for a test session and saves to timestamped file.
    Usage:
        logger = SessionLogger("test_session")
        logger.start()
        # ... run tests ...
        logger.stop()
    """
    
    def __init__(self, session_name: str):
        self.session_name = session_name
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("logs") / "test_sessions"
        self.log_file = self.log_dir / f"{session_name}_{self.timestamp}.txt"
        self.file_handler = None
        
    def start(self):
        """Start capturing logs to file"""
        # Create logs directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create file handler
        self.file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)
        
        # Format: timestamp - level - logger - message
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.file_handler.setFormatter(formatter)
        
        # Add to root logger (captures all logs)
        logging.getLogger().addHandler(self.file_handler)
        
        # Log session start
        logging.info(f"=" * 80)
        logging.info(f"SESSION START: {self.session_name}")
        logging.info(f"Timestamp: {self.timestamp}")
        logging.info(f"Log file: {self.log_file}")
        logging.info(f"=" * 80)
        
        return self.log_file
    
    def stop(self):
        """Stop capturing logs"""
        if self.file_handler:
            logging.info(f"=" * 80)
            logging.info(f"SESSION END: {self.session_name}")
            logging.info(f"=" * 80)
            
            # Remove handler
            logging.getLogger().removeHandler(self.file_handler)
            self.file_handler.close()
        
        return self.log_file
```

### 3.2 Create Test Runner Script with Logging

**New file**: `test_all_questions.py`

```python
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from main import run_census_query
from src.utils.session_logger import SessionLogger

def test_all_questions():
    # Start session logging
    session = SessionLogger("full_test_suite")
    log_file = session.start()
    
    print(f"Logging to: {log_file}")
    
    with open('test_questions/test_questions_new.csv', 'r') as f:
        reader = csv.DictReader(f)
        results = []
        
        for row in reader:
            question_no = row['No']
            question = row['Question friendly human']
            
            logging.info(f"\n{'='*60}")
            logging.info(f"TEST {question_no}: {question}")
            logging.info(f"{'='*60}")
            print(f"\nTesting Q{question_no}: {question}")
            
            try:
                result = run_census_query(question, user_id="test_user")
                success = result.get('final', {}).get('answer_text') is not None
                
                answer = result.get('final', {}).get('answer_text', 'No answer')
                charts = result.get('final', {}).get('generated_files', [])
                
                results.append({
                    'question_no': question_no,
                    'question': question,
                    'status': 'PASS' if success else 'FAIL',
                    'answer': answer,
                    'charts': charts
                })
                
                logging.info(f"Status: {'PASS' if success else 'FAIL'}")
                logging.info(f"Answer: {answer}")
                logging.info(f"Files generated: {charts}")
                
            except Exception as e:
                results.append({
                    'question_no': question_no,
                    'question': question,
                    'status': 'ERROR',
                    'error': str(e)
                })
                logging.error(f"Status: ERROR")
                logging.error(f"Error: {str(e)}", exc_info=True)
        
        # Report
        passed = sum(1 for r in results if r['status'] == 'PASS')
        failed = sum(1 for r in results if r['status'] in ['FAIL', 'ERROR'])
        
        summary = f"\n{'='*60}\nRESULTS: {passed}/{len(results)} passed, {failed} failed\n{'='*60}"
        print(summary)
        logging.info(summary)
        
        # Save detailed results
        results_file = Path("logs") / "test_sessions" / f"results_{session.timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logging.info(f"Detailed results saved to: {results_file}")
        
        # Stop session logging
        session.stop()
        
        print(f"\nComplete logs saved to: {log_file}")
        print(f"Results summary saved to: {results_file}")
        
        return passed == len(results)

if __name__ == '__main__':
    all_pass = test_all_questions()
    exit(0 if all_pass else 1)
```

### 3.3 Create Logs Directory Structure

**Create**: `logs/test_sessions/.gitkeep` (empty file to preserve directory in git)

**Expected structure after tests**:

```
logs/
  test_sessions/
    full_test_suite_20251102_143052.txt
    results_20251102_143052.json
    full_test_suite_20251102_150823.txt
    results_20251102_150823.json
```

**Log file format**:

```
2025-11-02 14:30:52 - INFO - root - ================================================================================
2025-11-02 14:30:52 - INFO - root - SESSION START: full_test_suite
2025-11-02 14:30:52 - INFO - root - Timestamp: 20251102_143052
2025-11-02 14:30:52 - INFO - root - Log file: logs/test_sessions/full_test_suite_20251102_143052.txt
2025-11-02 14:30:52 - INFO - root - ================================================================================
2025-11-02 14:30:53 - INFO - root - 
============================================================
2025-11-02 14:30:53 - INFO - root - TEST 1: What's the total population/age summary for the U.S. in 2023?
2025-11-02 14:30:53 - INFO - root - ============================================================
2025-11-02 14:31:05 - INFO - census_query_agent - Loading user memory for user_id: test_user
2025-11-02 14:31:07 - INFO - census_query_agent - Successfully parsed as direct JSON
...
2025-11-02 14:31:10 - INFO - root - Status: PASS
2025-11-02 14:31:10 - INFO - root - Answer: The U.S. population in 2023 is 331,097,593 according to ACS 1-Year estimates.
2025-11-02 14:31:10 - INFO - root - Files generated: ['Chart: data/charts/chart_bar_20251102_143110.png']
...
```

### 3.2 Test Question Categories

**Questions 1-50**: Single year, various geographies and table types

- **Expected**: Should work with Phase 1 fixes

**Questions 51-70**: Multi-year time series

- **Expected**: Require Phase 2 agent prompt updates
- **Key patterns**: "2015 to 2020", "since 2010", "2012-2023"

### 3.3 Progressive Testing Strategy

1. **Test Questions 1-10** (basic queries) after Phase 1

                                                                                                                                                                                                - Expected: 10/10 pass

2. **Test Questions 11-50** (complex geographies) after Phase 1

                                                                                                                                                                                                - Expected: 40/40 pass

3. **Test Questions 51-70** (time series) after Phase 2

                                                                                                                                                                                                - Expected: 20/20 pass

4. **Full test suite** (all 70)

                                                                                                                                                                                                - Expected: 70/70 pass before Nov 14

---

## Phase 4: Stability and Documentation (Day 6-7)

### 4.1 Verify No Regressions

**Run existing tests**:

```bash
uv run python -m pytest test/ -v
uv run python test_system.py
```

**Expected**: All existing tests still pass + 70 new questions pass.

### 4.2 Update Documentation

**File**: `docs/AGENT_OUTPUT_FORMAT.md`

**Add section** (after line 259):

````markdown
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
````

The chart generation automatically adapts to these custom column names.

````

### 4.3 Update ARCHITECTURE.md

**File**: `app_description/ARCHITECTURE.md`

**Update line 575** (example 5):

```markdown
5. "Show population trends for NYC from 2015 to 2020"
                                                                                 - Expected: Time series data with 6 data points
                                                                                 - Expected: Line chart generated automatically
                                                                                 - Expected: Agent makes 6 separate census_api_call invocations
                                                                                 - Expected: Data restructured as [["Year", "Population"], ["2015", "..."], ...]
````

---

## Phase 5: Final Validation (Day 8-10)

### 5.1 End-to-End Testing

**Run from main.py**:

```bash
# Test sample questions from each category
uv run python main.py
> What's the population of New York City?
> Show me median income trends from 2015 to 2020
> Compare population by county in California
```

**Verify**:

- Charts generate successfully (no "NAME" column errors)
- Multi-year queries produce line charts
- All 70 test questions pass

### 5.2 Performance Check

**Monitor**:

- Multi-year queries: ~5-10 seconds per year (acceptable)
- Large geography enumerations: <30 seconds for 58 California counties
- Memory usage: Should remain stable

### 5.3 Release Readiness Checklist

Before Nov 14 release:

- [ ] Phase 1 complete: Chart regression fixed
- [ ] Phase 2 complete: Multi-year queries working
- [ ] All 70 test questions pass (run `test_all_questions.py`)
- [ ] No regressions in existing functionality
- [ ] Documentation updated
- [ ] Performance acceptable (<30s for complex queries)

---

## Rollback Plan

If issues arise:

1. **Chart regression fix** is isolated to `src/nodes/output.py:get_chart_params()` - can revert single function
2. **Agent prompt changes** in `src/llm/config.py` - can revert AGENT_PROMPT_TEMPLATE
3. **Git checkpoint** before each phase for easy rollback

---

## Success Criteria

**Must achieve before Nov 14**:

- ✅ 70/70 test questions pass
- ✅ No chart generation errors
- ✅ Multi-year time series queries work
- ✅ All 144+ Census API configurations supported
- ✅ Application stable (no regressions)

**Evidence required**:

- `test_all_questions.py` output showing 70/70 PASS
- Terminal logs showing successful chart generation
- Example queries demonstrating time series charts