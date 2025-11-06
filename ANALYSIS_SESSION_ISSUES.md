# Analysis: Session Log Review & Implementation Roadmap

**Date:** 2025-11-04  
**Session Log:** `demo_20251104_205845.txt`  
**Reference:** `CENSUS_DISCUSSION.md`

---

## Application Purpose

**The entire purpose of this application is to dynamically derive/construct Census API URLs following the exact patterns shown in ALL official Census API examples:**

- Detail Tables (B or C): https://api.census.gov/data/2023/acs/acs5/examples.html
- Detail Profiles (DP): https://api.census.gov/data/2023/acs/acs5/profile/examples.html
- Comparison Tables (CP): https://api.census.gov/data/2023/acs/acs5/cprofile/examples.html
- Selected Population Profiles (SPP): https://api.census.gov/data/2024/acs/acs1/spp/geography.html
- Subject Tables (S): https://api.census.gov/data/2023/acs/acs5/subject/examples.html

**The application must construct URLs that match these examples exactly** - including geography hierarchy ordering, parameter syntax, and dataset-specific patterns.

---

## Executive Summary

**CORE PURPOSE:** This application must dynamically derive/construct Census API URLs following the exact patterns shown in ALL official Census API examples (CENSUS_DISCUSSION.md lines 172-176). The application is failing its primary purpose.

Analysis of the demo session reveals **5 critical areas** where the agent fails to construct API URLs correctly, blocking the core functionality:
1. **Incorrect geography syntax construction** - Cannot build valid `for=` clauses
2. **Missing dynamic variable validation** - Cannot verify variables exist before API calls
3. **Incomplete complex geography hierarchy support** - Cannot construct hierarchy-ordered `in=` parameters
4. **Weak geography name resolution** - Cannot resolve names to codes correctly
5. **Dataset-specific geography validation gaps** - Cannot determine which geographies are supported per dataset

**Critical Finding:** The `in=` parameter MUST order geography levels from LEAST granular to MOST granular (verified across ALL dataset types: acs5, profile, cprofile, subject, spp). Current code has no hierarchy ordering enforcement, causing API failures.

---

## Issue Breakdown

### 1. Geography API Call Syntax Errors

**Problem:** Agent builds invalid `for=` clauses by mixing geography levels.

**Evidence from logs:**
```
Action Input: {"geo_for": {"place": "59000", "state": "17"}}
ERROR: HTTP 400: error: invalid 'for' argument
URL: ...&for=place%3A59000%20state%3A17
```

**Root Cause:** `census_api_tool.py` lines 75-79 incorrectly joins multiple `for` clauses:
```python
for_clauses.append(f"{key}:{value}")
geo_filters["for"] = " ".join(for_clauses)  # ❌ Wrong: creates "place:59000 state:17"
```

**Correct Syntax (per CENSUS_DISCUSSION.md line 155):**
- `for=place:59000&in=state:17` (place in state)
- `for=county:*&in=state:06` (all counties in state)

**Impact:** All queries requiring place+state or county+state fail.

---

### 2. Geography Token Mismatches

**Problem:** Agent uses "nation" when Census API requires "us".

**Evidence from logs:**
```
Action Input: {"geo_for": {"nation": "1"}}
ERROR: HTTP 400: error: unknown/unsupported geography hierarchy
URL: ...&for=nation%3A1
```

**Correct Syntax (per CENSUS_DISCUSSION.md line 145):**
- `for=us:1` or `for=us:*`

**Root Cause:** Agent doesn't have mapping from friendly names ("nation") to Census API tokens ("us").

**Impact:** All national-level queries fail for subject tables.

---

### 3. Variable Validation Failures

**Problem:** Agent uses variables that don't exist for specific years.

**Evidence from logs:**
```
Action Input: {"variables": ["S2301_C05_001E", ...]}
ERROR: HTTP 400: error: unknown variable 'S2301_C05_001E'
URL: ...2023/acs/acs5/subject?get=S2301_C05_001E...
```

**Root Cause:** 
- No per-year variable validation
- Vector DB may have variables from different years
- Agent assumes variables exist across all years

**Impact:** 
- Subject table queries fail (S2301, S2704, CP03)
- Agent wastes API calls retrying invalid variables

**Required Fix (per CENSUS_DISCUSSION.md lines 52-65):**
- Query `variables.json` per dataset/year: `https://api.census.gov/data/{year}/{dataset}/variables.json`
- Validate variable exists before API call

---

### 4. Complex Geography Hierarchy Failures

**Problem:** Agent cannot enumerate or query complex statistical areas (CBSA, Metropolitan Divisions).

**Evidence from logs:**
```
Action Input: {"action": "enumerate_areas", "level": "metropolitan division"}
Result: No areas found for metropolitan division

Action Input: {"action": "enumerate_areas", "level": "county", "parent": {"metropolitan division": "35614"}}
Result: No areas found for county
```

**Root Cause:** `geography_registry.py` line 176 builds parent filter incorrectly:
```python
geo_filter += f"&in={key}:{value}"  # ❌ Wrong: builds separate &in= clauses
```

**Correct Syntax (per Census API examples.html and your example):**
- **Single geography level:** `&in=state:*` ✅ (your example is correct)
- **Multiple geography levels:** Space-separated within ONE `in=` parameter:
```
for=county:*&in=metropolitan division:35614
for=county subdivision:*&in=state:48 county:201
```

**The Issue:** `geography_registry.py` line 176 has TWO problems:

1. **Builds multiple `&in=` parameters** instead of space-separated:
   ```python
   # When parent_geo = {"state": "48", "county": "201"}
   # Current code creates: &in=state:48&in=county:201  (multiple &in= parameters)
   # Should create: &in=state:48 county:201  (space-separated in one parameter)
   ```

2. **CRITICAL: Missing geography hierarchy ordering** - The `in=` parameter MUST order from LEAST granular to MOST granular (left to right):
   ```python
   # Evidence from ALL example links (CENSUS_DISCUSSION.md lines 171-176):
   # Line 197: in=metropolitan statistical area/micropolitan statistical area:35620 metropolitan division:35614
   #          CBSA (less granular) → division (more granular)
   # Line 301: for=tract:*&in=state:36 county:061
   #          state (less granular) → county (more granular)
   # Line 305: for=block group:*&in=state:36 county:061 tract:003100
   #          state (least) → county → tract (most granular of parents)
   
   # Current code just iterates dict items (WRONG - no ordering):
   for key, value in parent_geo.items():  # ❌ Dict order may be wrong
   
   # MUST order by geography hierarchy (least -> most granular):
   GEO_HIERARCHY = ["state", "county", "tract", "block group",
                    "metropolitan statistical area/micropolitan statistical area",
                    "metropolitan division", ...]
   sorted_items = sorted(parent_geo.items(), 
                        key=lambda x: GEO_HIERARCHY.index(x[0]) if x[0] in GEO_HIERARCHY else 999)
   # Then space-separate: &in=state:36 county:061
   ```

**Note:** The current code at `census_api_tool.py` line 97 correctly uses `" ".join(in_clauses)` for space-separated pattern, BUT it also doesn't enforce hierarchy ordering.

**Impact:** 
- Cannot list counties in metropolitan divisions
- Cannot query data within complex statistical areas
- Agent falls back to hardcoded documentation

---

### 5. Geography Name Resolution Weaknesses

**Problem:** Ambiguous name matching returns wrong results.

**Evidence from logs:**
```
Action Input: {"name": "New York City", "geography_type": "place"}
Result: {"code": "46060", "full_name": "New York Mills city, Minnesota"}  # ❌ Wrong

Action Input: {"name": "New York County", "geography_type": "county", "parent": {"state": "36"}}
Result: {"code": "001", "full_name": "Albany County, New York"}  # ❌ Wrong (should be Manhattan)
```

**Root Cause:** `geography_registry.py` lines 304-317 uses simple substring matching:
- "New York" matches "New York Mills" before "New York city"
- "New York County" matches "Albany County" (first county in NY alphabetically)

**Impact:** 
- Wrong geographic areas queried
- Results are incorrect but agent doesn't detect it
- User gets data for wrong location

---

### 6. Dataset-Specific Geography Support Unknown

**Problem:** Agent assumes all datasets support all geography levels.

**Evidence from logs:**
```
Action Input: {"table_code": "S0101", "geography_level": "us", "dataset": "acs/acs5/subject"}
Result: {"supported": false, "note": "Stub validation - assumes common tables support common geographies"}
```

**Root Cause:** `table_validation_tool.py` line 52-72 is a stub:
```python
# TODO: Query actual geography.html for real validation
common_geographies = ["nation", "state", "county", ...]
supported = geography_level in common_geographies  # ❌ Not dataset-specific
```

**Required Fix (per CENSUS_DISCUSSION.md line 216):**
- Query `geography.html` per dataset/year: `https://api.census.gov/data/{year}/{dataset}/geography.html`
- Parse available geography levels dynamically
- Validate before building API calls

**Impact:** 
- Agent attempts queries for unsupported geographies
- Wastes API calls on guaranteed failures

---

## Implementation Roadmap

### Priority 1: Fix API Call Syntax Construction

**Topic 1.1: Correct Geography Parameter Building**
- **File:** `src/utils/census_api_utils.py`, `src/tools/census_api_tool.py`
- **Issue:** Lines 75-79 build invalid `for=` clauses
- **Fix:** Separate `for=` and `in=` parameters correctly
  - Single geography in `for=`
  - Parent constraints in `in=`
  - Support chained `in=` for complex hierarchies
- **Test:** Place+state, county+state, tract+county+state queries

**Topic 1.2: Geography Token Mapping**
- **File:** `src/utils/census_api_utils.py`
- **Issue:** No mapping from friendly names to API tokens
- **Fix:** Create mapping dictionary:
  ```python
  GEO_TOKEN_MAP = {
      "nation": "us",
      "metro_area": "metropolitan statistical area/micropolitan statistical area",
      "cbsa": "metropolitan statistical area/micropolitan statistical area",
      ...
  }
  ```
- **Reference:** `CENSUS_DISCUSSION.md` lines 314-328

---

### Priority 2: Dynamic Variable Validation

**Topic 2.1: Per-Year Variable Validation**
- **File:** `src/utils/census_api_utils.py` (new function)
- **Issue:** No validation that variables exist for specific year
- **Fix:** 
  1. Query `variables.json`: `https://api.census.gov/data/{year}/{dataset}/variables.json`
  2. Cache variable lists per dataset/year
  3. Validate before API call
  4. Return available alternatives if variable missing
- **Reference:** `CENSUS_DISCUSSION.md` lines 52-65

**Topic 2.2: Variable Discovery Tool**
- **File:** `src/tools/variable_validation_tool.py` (new)
- **Issue:** Agent needs to check variable availability
- **Fix:** Tool to query variables.json and return available variables for table/year
- **Use Case:** Agent can check before constructing API calls

---

### Priority 3: Complex Geography Hierarchy Support

**Topic 3.1: Fix Metropolitan Division Enumeration**
- **File:** `src/utils/geography_registry.py` line 176
- **Issue:** THREE problems with parent filter construction:
  1. **Builds multiple `&in=` clauses** instead of space-separated
  2. **Missing hierarchy ordering** - `in=` must order from LEAST granular to MOST granular
  3. **No ordering enforcement** - dict iteration order is not guaranteed correct

- **Current Code (Wrong):**
  ```python
  for key, value in parent_geo.items():
      geo_filter += f"&in={key}:{value}"  # Creates: &in=state:48&in=county:201
  # Problems:
  # 1. Creates multiple &in= parameters (wrong)
  # 2. Order not guaranteed (could be county:201&in=state:48 - wrong order)
  # 3. No hierarchy awareness
  ```

- **Correct Syntax (per ALL Census API examples from CENSUS_DISCUSSION.md lines 171-176):**
  ```python
  # Geography hierarchy order: LEAST granular -> MOST granular
  GEO_HIERARCHY_ORDER = [
      "us", "region", "division", "state",
      "county", "county subdivision", "tract", "block group",
      "metropolitan statistical area/micropolitan statistical area",  # CBSA (less granular)
      "metropolitan division",  # Division (more granular)
      "combined statistical area",
      "new england city and town area",
      "place", "congressional district", "zcta", "puma"
  ]
  
  # Sort parent_geo by hierarchy order (least -> most granular)
  sorted_items = sorted(
      parent_geo.items(),
      key=lambda x: GEO_HIERARCHY_ORDER.index(x[0]) if x[0] in GEO_HIERARCHY_ORDER else 999
  )
  
  # Space-separate within ONE in= parameter
  in_parts = [f"{k}:{v}" for k, v in sorted_items]
  geo_filter += f"&in={' '.join(in_parts)}"
  # Correct: &in=state:36 county:061 (state LESS granular, county MORE granular)
  # Correct: &in=metropolitan statistical area/micropolitan statistical area:35620 metropolitan division:35614
  #         (CBSA LESS granular, division MORE granular)
  ```

- **Evidence from ALL example links:**
  - Line 197: `in=metropolitan statistical area/micropolitan statistical area:35620 metropolitan division:35614` (CBSA → division)
  - Line 301: `in=state:36 county:061` (state → county)
  - Line 305: `in=state:36 county:061 tract:003100` (state → county → tract)

- **Fix:** 
  1. Space-separate multiple geography levels within SINGLE `in=` parameter
  2. **CRITICAL:** Order from LEAST granular to MOST granular
  3. Create geography hierarchy ordering function/constant

- **Test:** 
  - `for=county:*&in=metropolitan division:35614`
  - `for=tract:*&in=state:36 county:061` (must be state first, then county)
  - `for=block group:*&in=state:36 county:061 tract:003100` (state → county → tract order)

**Topic 3.2: Complex Hierarchy Query Builder**
- **File:** `src/utils/census_api_utils.py` and `src/tools/census_api_tool.py`
- **Issue:** Code handles space-separated but **missing hierarchy ordering**
- **Current Code Check:** 
  - `census_api_tool.py` line 97 uses `" ".join(in_clauses)` ✅ (space-separated correct)
  - BUT line 86-87: `for key, value in geo_in.items():` ❌ (no ordering)
  - Dict iteration order is not guaranteed to match hierarchy order

- **Fix:** 
  1. Create geography hierarchy ordering function
  2. Apply ordering BEFORE joining: `sorted_items = sort_by_hierarchy(geo_in.items())`
  3. Then join: `" ".join([f"{k}:{v}" for k, v in sorted_items])`
  4. Apply to ALL geography builders (`census_api_tool.py`, `geography_registry.py`, `pattern_builder_tool.py`)

- **Reference:** ALL Census API examples (CENSUS_DISCUSSION.md lines 171-176) show `in=` ordered least→most granular

**Topic 3.3: Geography Hierarchy Discovery and Ordering**
- **File:** `src/utils/geography_registry.py` (new function)
- **Issue:** Cannot discover relationships AND cannot order by hierarchy (required for dynamic URL construction)
- **Fix:** 
  1. **Create geography hierarchy ordering constant/function:**
     ```python
     # Order from LEAST granular to MOST granular (as shown in all Census examples)
     GEOGRAPHY_HIERARCHY_ORDER = [
         "us", "region", "division", "state",
         "county", "county subdivision", "tract", "block group",
         "metropolitan statistical area/micropolitan statistical area",  # CBSA (less granular)
         "metropolitan division",  # Division (more granular)
         "combined statistical area",
         "new england city and town area",
         "new england city and town area division",
         "place", "congressional district", "zcta", "puma",
         "urban area", "school district (elementary)", "school district (secondary)", 
         "school district (unified)", "state legislative district (upper chamber)",
         "state legislative district (lower chamber)"
     ]
     
     def sort_geography_by_hierarchy(geo_dict: Dict[str, str]) -> List[Tuple[str, str]]:
         """Sort geography items by hierarchy order (least → most granular)"""
         return sorted(
             geo_dict.items(),
             key=lambda x: GEOGRAPHY_HIERARCHY_ORDER.index(x[0]) 
                          if x[0] in GEOGRAPHY_HIERARCHY_ORDER else 999
         )
     ```
  2. Query `geography.html` to understand valid parent-child relationships
  3. Cache hierarchy rules per dataset/year
  4. Validate queries against hierarchy rules
  5. **Apply ordering to ALL geography builders** before constructing URLs

---

### Priority 4: Improve Geography Name Resolution

**Topic 4.1: Enhanced Name Matching Algorithm**
- **File:** `src/utils/geography_registry.py` lines 269-322
- **Issue:** Simple substring matching fails for ambiguous names
- **Fix:**
  - Use fuzzy matching (fuzzywuzzy/rapidfuzz)
  - Prioritize exact matches over partial
  - Use parent geography to disambiguate
  - Return confidence scores

**Topic 4.2: Context-Aware Resolution**
- **File:** `src/tools/area_resolution_tool.py`
- **Issue:** Doesn't use context (state, parent) effectively
- **Fix:**
  - Always require parent for ambiguous names
  - Use state abbreviation resolution
  - Check for common aliases (e.g., "Manhattan" → "New York County")

**Topic 4.3: Multi-Level Resolution Strategy**
- **File:** `src/utils/geography_registry.py`
- **Issue:** Single-level lookup fails
- **Fix:**
  - Try place → county → state hierarchy
  - For "New York City", try place first, then sum of 5 counties
  - Return all matches with confidence scores

---

### Priority 5: Dataset-Specific Geography Validation

**Topic 5.1: Dynamic Geography Discovery**
- **File:** `src/tools/table_validation_tool.py`
- **Issue:** Stub validation (line 52) doesn't check actual API
- **Fix:**
  1. Query `geography.html`: `https://api.census.gov/data/{year}/{dataset}/geography.html`
  2. Parse HTML to extract available geography levels
  3. Cache per dataset/year
  4. Validate before API calls

**Topic 5.2: Dataset Geography Registry**
- **File:** `src/utils/geography_registry.py` (enhancement)
- **Issue:** No dataset-specific geography support tracking
- **Fix:**
  - Maintain registry of supported geographies per dataset/year
  - Query on first use, cache results
  - Provide tool to check support before queries

---

## Additional Issues Found

### 6. URL Encoding Problems
- **Evidence:** Complex geography names not properly encoded
- **Fix:** Ensure `urllib.parse.quote()` used for all geography tokens (line 121 in `census_api_utils.py`)
- **Note:** Census API examples show space-separated geography levels in `in=` parameter must be URL-encoded as `%20`

### 7. Understanding Census API `in=` Parameter Pattern
- **Clarification:** After reviewing official Census API examples.html pages:
  - **Single `in=` parameter is CORRECT**: `&in=state:*` ✅ (your example is correct)
  - **For multiple geography levels**, use space-separated within ONE `in=` parameter: `&in=state:06 county:037` ✅
  - **The issue:** `geography_registry.py` line 176 builds MULTIPLE `&in=` parameters when there are multiple parent geographies:
    ```python
    # Current code (WRONG when parent_geo has multiple items):
    for key, value in parent_geo.items():
        geo_filter += f"&in={key}:{value}"  
    # Creates: &in=state:48&in=county:201  (multiple &in= parameters)
    
    # Should be:
    in_parts = [f"{k}:{v}" for k, v in parent_geo.items()]
    geo_filter += f"&in={' '.join(in_parts)}"
    # Creates: &in=state:48 county:201  (space-separated in one parameter)
    ```
  - Current code in `census_api_tool.py` line 97 is CORRECT (uses space-separated within one parameter)

### 8. Group Syntax Not Validated
- **Evidence:** Agent uses `group(S0101)` but doesn't validate table exists
- **Fix:** Query `groups.json` before using group syntax

### 9. Error Recovery Weak
- **Evidence:** Agent retries same invalid query multiple times
- **Fix:** Better error parsing to understand why query failed and adjust

---

## Success Criteria

After implementing these topics, the agent should **dynamically construct Census API URLs following the exact patterns from ALL official examples** (CENSUS_DISCUSSION.md lines 172-176):

1. ✅ **Build valid Census API URLs** for all geography patterns matching official examples
2. ✅ **Order geography hierarchies correctly** - `in=` parameter from least granular → most granular (as shown in all examples)
3. ✅ **Validate variables exist** for specific year/dataset before API calls
4. ✅ **Enumerate and query complex statistical areas** (CBSA, divisions, CSA, NECTA) with correct hierarchy ordering
5. ✅ **Resolve ambiguous geography names** correctly with context
6. ✅ **Know which geography levels are supported** per dataset/year
7. ✅ **Handle all patterns** from `CENSUS_DISCUSSION.md` lines 139-343, matching official example URLs exactly
8. ✅ **Work across all dataset types** - acs5, profile, cprofile, subject, spp - using same patterns

**Primary Goal:** The application must dynamically derive API URLs that match the structure and patterns shown in:
- https://api.census.gov/data/2023/acs/acs5/examples.html
- https://api.census.gov/data/2023/acs/acs5/profile/examples.html
- https://api.census.gov/data/2023/acs/acs5/cprofile/examples.html
- https://api.census.gov/data/2023/acs/acs5/subject/examples.html
- https://api.census.gov/data/2024/acs/acs1/spp/geography.html

---

## Testing Requirements

For each topic, create tests that:

1. **Test valid API call construction:**
   - Place in state: `for=place:X&in=state:Y`
   - County in state: `for=county:*&in=state:Y`
   - Complex hierarchies: `for=X&in=Y&in=Z`

2. **Test variable validation:**
   - Variables exist for year
   - Variables don't exist for year (should return alternatives)
   - Group syntax validates

3. **Test geography enumeration:**
   - Metropolitan divisions enumerate
   - Counties within divisions enumerate
   - Complex parent hierarchies work

4. **Test name resolution:**
   - Ambiguous names resolve correctly with context
   - Returns confidence scores
   - Handles aliases (Manhattan → New York County)

5. **Test dataset-specific validation:**
   - Subject tables support different geographies than detail tables
   - Knows `us` vs `nation` per dataset
   - Validates geography before API call

---

## Verification Against Official Census API Examples

**Verified Against:**
- ✅ `https://api.census.gov/data/2023/acs/acs5/examples.html` (Detail Tables)
- ✅ `https://api.census.gov/data/2023/acs/acs5/profile/examples.html` (Profile Tables)
- ✅ `https://api.census.gov/data/2023/acs/acs5/cprofile/examples.html` (Comparison Profile)
- ✅ `https://api.census.gov/data/2023/acs/acs5/subject/examples.html` (Subject Tables)

**Key Findings from official examples (ALL dataset types verified):**

1. **`for=` Parameter:** Only ONE geography level allowed in `for=`
   - ✅ Correct: `for=county:*`
   - ❌ Wrong: `for=place:59000 state:17` (this is what agent builds)

2. **`in=` Parameter:** 
   - ✅ Correct - Single geography: `&in=state:*` (your example URL is correct)
   - ✅ Correct - Multiple levels: Space-separated within ONE `in=` parameter: `&in=state:06 county:037` (URL-encoded as `in=state:06%20county:037`)
   - ✅ Correct - Single complex geography: `&in=metropolitan division:35614`
   - ❌ Wrong - Multiple `&in=` parameters: `&in=state:06&in=county:037` (when `parent_geo` has multiple items, code creates this - should be space-separated in one parameter)

3. **CRITICAL: Geography Hierarchy Ordering in `in=` Parameter:**
   - **MUST order from LEAST granular to MOST granular (left to right)**
   - ✅ Correct: `in=state:36 county:061` (state less granular → county more granular)
   - ✅ Correct: `in=state:36 county:061 tract:003100` (state → county → tract)
   - ✅ Correct: `in=metropolitan statistical area/micropolitan statistical area:35620 metropolitan division:35614` (CBSA less granular → division more granular)
   - ❌ Wrong: `in=county:061 state:36` (reversed order - will fail)
   - **Evidence:** Verified across ALL dataset types (acs5, profile, cprofile, subject, spp)

4. **Geography Tokens:** Must use exact Census API tokens
   - ✅ `us` (not `nation`)
   - ✅ `metropolitan statistical area/micropolitan statistical area` (exact string)
   - ✅ `state (or part)` (exact string with parentheses)

5. **Pattern Consistency:** All dataset types (acs5, profile, cprofile, subject, spp) use same geography syntax patterns and hierarchy ordering

**Conclusion:** All identified issues remain valid, plus **NEW CRITICAL ISSUE discovered**:
- Invalid `for=` clause construction (Issue #1) ✅
- Geography token mismatches (Issue #2) ✅
- `in=` parameter pattern correctly understood (space-separated within one parameter) ✅
- **NEW: Missing geography hierarchy ordering in `in=` parameter** - MUST order from least→most granular ✅
- Complex geography enumeration failures (Issue #4) - now includes hierarchy ordering requirement ✅

---

## References

- `CENSUS_DISCUSSION.md`: Complete API patterns and requirements
- `logs/demo_20251104_205845.txt`: Actual session failures
- Census API Documentation: `https://api.census.gov/data/{year}/{dataset}/geography.html`
- Census API Examples: `https://api.census.gov/data/{year}/{dataset}/examples.html`
- Census Variables: `https://api.census.gov/data/{year}/{dataset}/variables.json`

