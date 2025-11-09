# Census API URL Construction - Comprehensive Stabilization Plan

## Overview

Fix the core purpose of the Census Tool: dynamically construct correct Census API URLs matching official examples. Address all 5 critical issues comprehensively while prioritizing geography hierarchy ordering and API URL syntax as highest impact.

**Key Update**: Variables are ALREADY stored in ChromaDB `census_vars` collection with year/dataset metadata - leverage existing infrastructure for validation.

**Timeline**: 2-3 weeks

**Target**: Pass Phase 2 QA with stable API URL construction

---

## PRIORITY 1: Geography Hierarchy & API URL Syntax (HIGHEST IMPACT)

### 1.1: Build Geography Hierarchy Vector Database

**Files**: `index/build_geography_hierarchy_index.py` (NEW), `config.py`

**Implementation**:

- Parse all 5 examples.md files (DETAIL_TABLES, DETAIL_PROFILES, SUBJECT_TABLES, COMPARISON_TABLES, SELECTED_POPULATION_PROFILES)
- Extract Geography Hierarchy patterns and ordering relationships from example URLs
- Store in NEW ChromaDB collection `census_geography_hierarchies` with metadata:
  - `year`, `dataset`, `geography_hierarchy`, `for_level`, `ordering_list`, `example_url`
- Support multiple years (2018-2024) and all dataset types
- **Critical**: Capture relationship-based ordering (NOT fixed least→most granular)

**Example Document**:

```python
{
  "document": "Geography hierarchy: metropolitan statistical area/micropolitan statistical area › metropolitan division › state (or part) › county. Ordering: CBSA then division then state. Example: for=county:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:31080%20metropolitan%20division:31084%20state%20(or%20part):06",
  "metadata": {
    "year": "2023",
    "dataset": "acs/acs5",
    "geography_hierarchy": "metropolitan statistical area/micropolitan statistical area › metropolitan division › state (or part) › county",
    "for_level": "county",
    "ordering_list": ["metropolitan statistical area/micropolitan statistical area", "metropolitan division", "state (or part)"],
    "example_url": "for=county:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:31080%20metropolitan%20division:31084%20state%20(or%20part):06"
  }
}
```

**Add to config.py**:

```python
CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME = "census_geography_hierarchies"
```

**Evidence of Success**: Collection exists with 300+ hierarchy patterns indexed

---

#### 1.1.B Runbook: Census Geography Hierarchy Ingestion
1. Pull dataset/year ranges from `config.py` (`DEFAULT_DATASETS`).
2. Run `python scripts/extract_census_examples.py --log-dir chroma_logs --output app_description`.  
   - Generates `chroma_logs/YYYYMMDD-HHMMSS-fetch.txt` with per-URL status (success, HTTP error, parsing error).  
   - Writes one markdown file per `(dataset, year)` under `app_description`.
3. Inspect log file:
   - `SUCCESS` → markdown ready.  
   - `FETCH_ERROR` → retry after network check.  
   - `PARSE_ERROR` → review HTML change; update parser before re-running.
4. Convert markdown rows into structured documents:
   - Fields: `table_category`, `year`, `geography_hierarchy`, `geography_level`, `ordering_list`, `example_url`, `retrieved_at`.
   - Upsert into Chroma collection `census_geography_hierarchies`.
5. Re-run the ingestion whenever Census publishes new examples. Keep all log files for audit.



### 1.2: Fix Geography API URL Construction Bugs

**Files**: `src/tools/census_api_tool.py`, `src/utils/census_api_utils.py`, `src/utils/geography_registry.py`, `src/tools/pattern_builder_tool.py`

**Critical Bugs to Fix**:

1. **census_api_tool.py lines 74-79** - INVALID `for=` clause construction:

   - Current: Creates `for=place:59000 state:17` (WRONG - multiple levels in for=)
   - Fix: Only ONE geography level in `for=`, rest go in `in=`
   - Logic: If geo_for has multiple items, identify target level and move parents to geo_in

2. **All URL builders** - Missing hierarchy ordering:

   - Current: `for key, value in geo_in.items():` (dict order not guaranteed)
   - Fix: Query geography hierarchy collection for ordering pattern
   - Apply correct relationship-based ordering before building `in=` parameter

3. **geography_registry.py line 176** - Multiple `&in=` parameters:

   - Current: `geo_filter += f"&in={key}:{value}"` (creates &in=state:06&in=county:073)
   - Fix: Space-separate within SINGLE `in=` parameter: `&in=state:06 county:073`

**Implementation Steps**:

- Create `get_hierarchy_ordering()` function in chroma_utils.py that queries geography hierarchy collection
- Add `validate_and_fix_geo_params()` to restructure geo_for/geo_in correctly
- Apply hierarchy ordering to all geography builders
- Add geography token mapping (nation→us, cbsa→metropolitan statistical area/micropolitan statistical area)
- ✅ Shared helper `build_geo_filters()` now routes all URL builders through hierarchy-aware ordering
- ✅ Geography producers (geo utils mappings, enumeration detector, registry enumeration) now emit canonical dictionaries plus pre-encoded filters
- ✅ Unit coverage added for hierarchy lookup (`test_chroma_utils.py`), geography hint resolution (`test_geo_utils.py`), and enumeration filters (`test_enumeration_detector.py`)

**Evidence of Success**: Test URLs match official examples exactly, no 400 errors on geography syntax

---

### 1.3: Create Geography Hierarchy Query Tool

**Files**: `src/tools/geography_hierarchy_tool.py` (NEW)

**Purpose**: Allow agent to query correct hierarchy ordering before constructing API URLs

**Tool Interface**:

```python
{
  "action": "get_hierarchy_ordering",
  "year": 2023,
  "dataset": "acs/acs5",
  "for_level": "county",
  "parent_levels": [
    "metropolitan statistical area/micropolitan statistical area",
    "state (or part)"
  ]  # use plain "state" when the hierarchy stays within a single state
}
```

**Returns**:

```python
{
  "ordered_parents": ["metropolitan statistical area/micropolitan statistical area", "state (or part)"],
  "example_url": "for=county:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:31080%20state%20(or%20part):06",
  "geography_hierarchy": "metropolitan statistical area/micropolitan statistical area › state (or part) › county"
}
```

**Status**: COMPLETE ✅
- Implemented `src/tools/geography_hierarchy_tool.py` invoking `get_hierarchy_ordering`
- Tool registered inside `CensusQueryAgent`
- Added unit tests (`test_geography_hierarchy_tool.py`)

**Evidence of Success**: Agent can query `geography_hierarchy` tool to confirm parent ordering (e.g., county → metro division → metro area → state (or part)) before building URLs.

---

## PRIORITY 2: Variable Validation (Leverage EXISTING ChromaDB Collection)

### 2.1: Build Variable Validation System Using Existing census_vars Collection

**Files**: `src/utils/variable_validator.py` (NEW), `src/tools/variable_validation_tool.py` (NEW)

**Key**: Variables are ALREADY indexed in `census_vars` collection with metadata:

- `var`: Variable code (e.g., "B01003_001E")
- `label`: Variable description
- `concept`: Table concept
- `dataset`: Dataset path (e.g., "acs/acs5")
- `years_available`: Comma-separated string (e.g., "2018,2019,2020,2021,2022,2023")

**Implementation** - Query EXISTING `census_vars` collection:

```python
collection = get_chroma_collection_variables(client)

# Query specific variables
results = collection.get(
    where={
        "$and": [
            {"var": {"$in": ["S2301_C05_001E", "S2301_C05_002E"]}},
            {"dataset": "acs/acs5/subject"}
        ]
    },
    include=["metadatas"]
)

# Check if year in metadata["years_available"].split(",")
for metadata in results["metadatas"]:
    years = metadata["years_available"].split(",")
    if str(year) not in years:
        # Variable invalid for this year
```

**Tool Interface**:

```python
{
  "action": "validate_variables",
  "year": 2023,
  "dataset": "acs/acs5/subject",
  "variables": ["S2301_C05_001E", "S2301_C05_002E"]
}
```

**Returns**:

```python
{
  "valid": ["S2301_C05_001E"],
  "invalid": ["S2301_C05_002E"],
  "alternatives": {
    "S2301_C05_002E": ["S2301_C04_001E", "S2301_C03_001E"]  # Same table/concept
  },
  "years_available": {
    "S2301_C05_001E": ["2018", "2019", "2020", "2021", "2022", "2023"]
  }
}
```

**Status**: COMPLETE ✅
- `validate_variables()` helper queries `census_vars` with live variables.json fallback
- `variable_validation` LangChain tool exposes validation/list actions
- Agent toolset updated to include variable validation
- Unit tests cover helper, tool, alternatives, and filtering

**Evidence of Success**: `test_variable_validator.py` + `test_variable_validation_tool.py` pass; validation tool now available to agent.

---

### 2.2: Integrate Validation into Agent Workflow

**Files**: `src/llm/config.py` (agent prompt), `src/utils/agents/census_query_agent.py`

**Status**: COMPLETE ✅
- Prompt now documents `variable_validation` tool with required JSON schema
- Added directive: run `variable_validation` immediately before `pattern_builder`/`census_api_call` and resolve invalid variables first
- Tool already registered in `CensusQueryAgent`

**Evidence of Success**: Updated prompt guides reasoning to validate variables pre-URL construction

---

## PRIORITY 3: Complex Geography Support

### 3.1: Fix Geography Registry Enumeration

**Files**: `src/utils/geography_registry.py`, `app_test_scripts/test_geography_registry.py`

**Status**: COMPLETE ✅
- `enumerate_areas` now canonicalizes parents via `validate_and_fix_geo_params` (hierarchy-aware)
- Telemetry events emitted for cache hits, API calls, and failures
- Added unit test covering multi-level parents (CBSA → division → state)

**Evidence of Success**: Test `test_enumerate_areas_orders_parents` passes; telemetry logs include ordered parents and URL.

---

### 3.2: Dataset-Specific Geography Support Validation

**Files**: `src/utils/dataset_geography_validator.py` (NEW), `src/tools/table_validation_tool.py`, `app_test_scripts/test_dataset_geography_validator.py`, `app_test_scripts/test_table_validation_tool.py`

**Status**: COMPLETE ✅
- Added geography validator that scrapes `geography.html`, caches results (memory + disk), and logs telemetry
- `table_validation_tool` now returns dataset/year-aware validation results with telemetry
- Unit tests cover cache usage, network failure fallback, and tool integration

**Evidence of Success**: Tests `test_dataset_geography_validator.py` and `test_table_validation_tool.py` pass; telemetry events recorded for validations

---

## PRIORITY 4: Geography Name Resolution

### 4.1: Enhanced Name Matching

**Files**: `src/utils/geography_registry.py` lines 269-322

**Improvements**:

- Use fuzzy matching (rapidfuzz library) for ambiguous names
- Prioritize exact matches over partial matches
- Use parent geography context to disambiguate
- Return confidence scores with all matches
- Handle common aliases (Manhattan→New York County, NYC→5 counties)

**Evidence of Success**: "New York City" resolves correctly with context

---

### 4.2: Multi-Level Resolution Strategy

**Files**: `src/tools/area_resolution_tool.py`

**Enhancements**:

- Try hierarchical resolution (place → county → state)
- For multi-county areas, return all component geographies
- Require parent context for ambiguous names
- Validate resolved codes exist in enumeration

**Evidence of Success**: Ambiguous names resolve correctly with parent context

---

## PRIORITY 5: Agent Prompt Enhancements

### 5.1: Update Agent Instructions

**Files**: `src/llm/config.py`

**Add Sections**:

1. **Geography Hierarchy Reasoning**: Query hierarchy tool before building URLs
2. **Variable Validation Step**: Validate variables exist for year/dataset using validation tool
3. **Geography Token Mapping**: Use correct Census API tokens (us not nation)
4. **Error Recovery**: Parse API errors and adjust parameters
5. **URL Construction Examples**: Show correct patterns from all 5 example types

**Evidence of Success**: Agent reasoning traces show hierarchy queries and validation

---

## Testing & Validation

### Test Strategy:

1. **Unit Tests**: Test each URL builder with official example patterns
2. **Integration Tests**: Test full agent workflow with 70 test questions
3. **Validation Tests**: Compare constructed URLs to official examples
4. **Regression Tests**: Ensure existing functionality still works

### Success Criteria:

- ✅ All constructed URLs match official example patterns
- ✅ No 400 errors on geography syntax
- ✅ No "unknown variable" errors
- ✅ Complex hierarchies (CBSA, Metro Divisions) work correctly
- ✅ Ambiguous geography names resolve correctly
- ✅ 70/70 test questions pass with REAL API data (not fallback answers)

### Test Evidence Files:

- `logs/test_sessions/phase2_qa_validation_[timestamp].txt`
- `logs/url_validation/constructed_vs_official_[timestamp].json`
- `logs/api_errors/error_analysis_[timestamp].txt`

---

## Implementation Order

**Week 1**: Priority 1 (Geography Hierarchy & URL Syntax)

- Days 1-2: Build geography hierarchy vector DB (1.1)
- Days 3-4: Fix URL construction bugs (1.2)
- Day 5: Create hierarchy query tool (1.3)

**Week 2**: Priorities 2 & 3 (Validation & Complex Geography)

- Days 1-2: Variable validation system using census_vars collection (2.1, 2.2)
- Days 3-4: Fix geography registry (3.1, 3.2)
- Day 5: Testing and bug fixes

**Week 3**: Priorities 4 & 5 + Final Validation

- Days 1-2: Name resolution improvements (4.1, 4.2)
- Day 3: Agent prompt enhancements (5.1)
- Days 4-5: Full QA testing, regression testing, documentation

---

## Existing ChromaDB Collections

**Current Collections**:

1. `census_vars` - Variables indexed with year/dataset metadata (LEVERAGE FOR VALIDATION)
2. `census_tables` - Tables indexed by table code

**New Collection**:

3. `census_geography_hierarchies` - Geography hierarchy patterns (NEW - Priority 1)

---

## Rollback Plan

Each priority is isolated:

- Priority 1: New collection + function changes (can revert URL builders)
- Priority 2: New validation tool (queries existing collection - can disable)
- Priority 3: Geography registry enhancements (can revert single file)
- Priority 4: Name matching improvements (can revert single file)
- Priority 5: Agent prompt changes (can revert single template)

---

## Key Deliverables

1. Geography hierarchy vector DB collection with 300+ patterns
2. Fixed URL construction in 4 files (census_api_tool, census_api_utils, geography_registry, pattern_builder_tool)
3. Variable validation system leveraging existing census_vars collection
4. Geography hierarchy query tool for agent
5. Enhanced name resolution with fuzzy matching
6. Updated agent prompt with hierarchy reasoning
7. Comprehensive test suite validating URL construction
8. Documentation of all changes with examples

---

## Notes

- **All changes must reference official Census API examples** from the 5 examples.md files
- **Test against actual API** - no mock data, verify real API calls succeed (when validating phases execution)
- **Validate URL structure** - compare constructed URLs character-by-character to official examples
- **Document edge cases** - capture any special patterns or exceptions discovered during testing