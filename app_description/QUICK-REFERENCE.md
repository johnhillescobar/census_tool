# Quick Reference: Census Tool Remediation

## TL;DR - What's Wrong and How to Fix It

### The Problem (in 3 sentences)
1. **Wrong Search Level**: Your system searches 20,000+ individual variables instead of ~500 Census tables → poor accuracy
2. **Missing Categories**: Only supports Detail Tables (B/C), missing 80% of Census data (Subject, Profile, Comparison, SPP)
3. **Static URLs**: Cannot build API calls for different data categories → limited data access

### The Solution (in 3 sentences)
1. **Phase 8** (2-3 weeks): Rebuild ChromaDB to search tables first, then variables → accuracy 53% → 67%
2. **Phase 9** (2-3 weeks): Add all 5 Census categories + Groups API + dynamic URLs → accuracy 67% → 92%
3. **Result**: Accurate, flexible tool that works with natural language and accesses all Census data

---

## Current vs. Target Architecture

### Current (Limited) 🔴
```
User Query
    ↓
Search 20,000 variables in ChromaDB ❌ (Wrong level)
    ↓
Select variable (often wrong)
    ↓
Build URL for acs/acs5 only ❌ (Missing categories)
    ↓
Fetch data (Limited to Detail Tables)
```

### Target (Comprehensive) ✅
```
User Query
    ↓
Detect category (detail, subject, profile, etc.) ✅
    ↓
Search ~500 tables in ChromaDB ✅ (Right level)
    ↓
Select table (high accuracy)
    ↓
Choose variables within table ✅
    ↓
Build dynamic URL for any category ✅
    ↓
Fetch data (All Census categories)
```

---

## The 5 Census Categories You're Missing

| Category | Current | Missing | Example Use Case |
|----------|---------|---------|------------------|
| **Detail Tables (B/C)** | ✅ Have it | - | "Population of NYC by age group" |
| **Subject Tables (S)** | ❌ None | 🔴 CRITICAL | "Give me a demographic overview of Texas" |
| **Profile Tables (DP)** | ❌ None | 🔴 CRITICAL | "Show me a full demographic profile of California" |
| **Comparison (CP)** | ❌ None | 🟡 Important | "Compare income changes 2015-2020" |
| **Population Profiles (S0201)** | ❌ None | 🟡 Important | "Hispanic population statistics in Florida" |

**Impact**: You have 20% of available data, need 100%

---

## Key API Differences

### What You're Currently Using
```bash
# Only Detail Tables
https://api.census.gov/data/2023/acs/acs5?get=B01003_001E&for=state:06
```

### What You're Missing

```bash
# Subject Tables (overview data)
https://api.census.gov/data/2023/acs/acs5/subject?get=group(S0101)&for=state:06

# Profile Tables (comprehensive profiles)
https://api.census.gov/data/2023/acs/acs1/profile?get=group(DP05)&for=state:06

# Comparison Tables (multi-year)
https://api.census.gov/data/2023/acs/acs5/cprofile?get=group(CP03)&for=state:06

# Population Profiles (race/ethnicity specific)
https://api.census.gov/data/2023/acs/acs1/spp?get=group(S0201)&for=state:06
```

**Key Difference**: You're missing `/subject`, `/profile`, `/cprofile`, `/spp` paths and `group()` function

---

## Implementation Priority Matrix

| Phase | Priority | Duration | Accuracy Gain | Complexity |
|-------|----------|----------|---------------|------------|
| **Phase 8**: Table Architecture | 🔴 CRITICAL | 2-3 weeks | +14% (53→67%) | Medium |
| **Phase 9**: Multi-Category | 🔴 CRITICAL | 2-3 weeks | +25% (67→92%) | Medium-High |

**Total**: 4 weeks, +39% accuracy improvement

---

## Quick Decision Guide

### Should I Start Phase 8 or Phase 9 First?

**Answer**: ALWAYS Phase 8 first!

**Why**: Phase 9 depends on Phase 8's table-level architecture. Building multi-category support on a variable-level system won't help much.

```
Wrong Order: ❌
Phase 9 (multi-category) → Still searching variables → Poor accuracy

Right Order: ✅
Phase 8 (table-level) → Phase 9 (multi-category) → High accuracy
```

---

## Files You Need to Create/Modify

### Phase 8: Table-Level Architecture

**Create**:
- `src/utils/census_groups_api.py` - Fetch groups.json and table metadata
- `index/build_index_tables.py` - Build table-level ChromaDB index
- `test_table_retrieval.py` - Test table matching

**Modify**:
- `config.py` - Add table-level settings
- `src/nodes/retrieve.py` - Search tables, then select variables
- `src/state/types.py` - Add table_code field

**Run**:
```bash
python index/build_index_tables.py  # Rebuild index
python test_table_retrieval.py       # Verify accuracy
```

### Phase 9: Multi-Category Support

**Create**:
- `src/utils/category_selector.py` - Choose best Census category
- `test_category_selection.py` - Test category detection

**Modify**:
- `config.py` - Add CENSUS_CATEGORIES config
- `src/utils/census_api_utils.py` - Dynamic URL builder
- `src/state/types.py` - Add category field
- `src/nodes/data.py` - Support multiple categories
- `index/build_index_tables.py` - Index multiple categories

**Run**:
```bash
python index/build_index_tables.py  # Rebuild with all categories
python test_category_selection.py    # Test category routing
```

---

## Expected Results

### Before (Current System)
```python
# Query: "What's the population of NYC?"
# Problem: Searches 20,000 variables, might find B07407_007E (migration variable)
# Accuracy: ~60%
# API Call: Sometimes wrong variable
```

### After Phase 8
```python
# Query: "What's the population of NYC?"
# Improved: Searches ~500 tables, finds B01003 (Total Population)
# Accuracy: ~85%
# API Call: Correct table, but still limited to detail tables
```

### After Phase 9
```python
# Query: "Give me a demographic overview of NYC"
# Optimal: Detects "overview" → selects Subject category → finds S0101
# Accuracy: ~95%
# API Call: /acs/acs5/subject?get=group(S0101)&for=place:51000&in=state:36
```

---

## Common Pitfalls to Avoid

### ❌ Don't Do This
1. **Skip Phase 8 and go straight to Phase 9**
   - Phase 9 needs table-level foundation
   
2. **Try to modify existing variable-level code**
   - Clean rebuild is faster and more reliable
   
3. **Build all 5 categories at once**
   - Start with Detail + Subject, add others incrementally

4. **Forget to rebuild the ChromaDB index**
   - Old variable-level index won't work with new code

5. **Test only with table codes (B01003)**
   - Test with natural language: "people living in", "overview of demographics"

### ✅ Do This Instead
1. **Complete Phase 8 fully before Phase 9**
   - Verify table retrieval works
   
2. **Create new files alongside old ones**
   - Keep old system working during transition
   
3. **Test incrementally**
   - Test each component as you build

4. **Start with 2 categories (detail + subject)**
   - Prove concept, then add profile/cprofile/spp

5. **Use natural language test queries**
   - "population of", "overview of", "Hispanic people in"

---

## Quick Start Commands

### Phase 8 Quick Start
```bash
# 1. Create new Groups API fetcher
# Copy template from IMPLEMENTATION-TEMPLATES.md section "Template 2"
touch src/utils/census_groups_api.py

# 2. Create new table-level index builder
# Copy template from IMPLEMENTATION-TEMPLATES.md section "Template 3"
touch index/build_index_tables.py

# 3. Build table-level index
python index/build_index_tables.py

# 4. Update retrieve node
# Copy template from IMPLEMENTATION-TEMPLATES.md section "Template 4"
# Modify src/nodes/retrieve.py

# 5. Test
python -c "from src.nodes.retrieve import retrieve_node_table_level; print('Success!')"
```

### Phase 9 Quick Start
```bash
# 1. Update config with categories
# Copy template from IMPLEMENTATION-TEMPLATES.md section "Template 5"
# Add to config.py

# 2. Create category selector
# Copy template from IMPLEMENTATION-TEMPLATES.md section "Template 6"
touch src/utils/category_selector.py

# 3. Update API utils for dynamic URLs
# Copy template from IMPLEMENTATION-TEMPLATES.md section "Template 7"
# Modify src/utils/census_api_utils.py

# 4. Test category selection
python src/utils/category_selector.py

# 5. Rebuild index with all categories
python index/build_index_tables.py --all-categories
```

---

## Testing Checklist

### Phase 8 Tests ✅
```python
# Test 1: Population query finds B01003
assert "B01003" in retrieve_tables("population")

# Test 2: Income query finds B19013
assert "B19013" in retrieve_tables("median income")

# Test 3: Natural language works
assert "B01003" in retrieve_tables("people living in")

# Test 4: Confidence scores reasonable
assert top_result_confidence > 0.7
```

### Phase 9 Tests ✅
```python
# Test 1: "overview" selects subject category
assert select_category("overview") == "subject"

# Test 2: "Hispanic" selects SPP category
assert select_category("Hispanic population") == "spp"

# Test 3: URL builder handles all categories
assert "/subject?" in build_url(category="subject")
assert "/profile?" in build_url(category="profile")

# Test 4: group() function used correctly
assert "group(S0101)" in build_url(groups=["S0101"])
```

---

## Troubleshooting Guide

### Problem: "ChromaDB collection not found"
**Solution**: Rebuild index with `python index/build_index_tables.py`

### Problem: "Still getting wrong variables"
**Check**: 
1. Did you rebuild ChromaDB index? (Most common issue)
2. Are you using new retrieve_node_table_level?
3. Is query going through table search first?

### Problem: "Subject tables not working"
**Check**:
1. Did you add CENSUS_CATEGORIES to config?
2. Is category_selector returning "subject"?
3. Is URL builder using `/subject` path?

### Problem: "Low accuracy after Phase 8"
**Check**:
1. Run test queries with known answers
2. Check ChromaDB contains tables not variables
3. Verify table descriptions are searchable
4. Look at distances/confidence scores

### Problem: "API returns 400 error"
**Check**:
1. Print the actual URL being called
2. Verify path is correct for category
3. Test URL directly in browser
4. Check geography format matches category requirements

---

## Success Metrics

### Phase 8 Success Criteria
- [ ] ChromaDB has ~450-500 tables (not 20,000 variables)
- [ ] Query "population" returns B01003 as top result
- [ ] Query "income" returns B19013 as top result
- [ ] Confidence scores >0.7 for correct matches
- [ ] Natural language queries work (no variable codes needed)

### Phase 9 Success Criteria
- [ ] All 5 categories configured in config.py
- [ ] Category selector returns correct category >85% of time
- [ ] URL builder creates valid URLs for all categories
- [ ] "overview" queries use subject tables
- [ ] "Hispanic" queries use SPP tables
- [ ] End-to-end test passes for all categories

---

## Resources

### Documentation
- **Main Roadmap**: `ARCHITECTURE-REMEDIATION-ROADMAP.md`
- **Phase 8 Details**: `PHASE8-ChromaDB-Architecture-Fix.md`
- **Phase 9 Details**: `PHASE9-Census-API-Flexibility-Analysis.md`
- **Code Templates**: `IMPLEMENTATION-TEMPLATES.md`
- **Census API Background**: `CENSUS_DISCUSSION.md`

### Census API References
- **Table IDs**: https://www.census.gov/programs-surveys/acs/data/data-tables/table-ids-explained.html
- **API Docs**: https://www.census.gov/data/developers/data-sets.html
- **Examples**: https://api.census.gov/data/2023/acs/acs5/examples.html

### Test Endpoints
```bash
# Detail tables groups
curl "https://api.census.gov/data/2023/acs/acs5/groups.json"

# Subject tables groups
curl "https://api.census.gov/data/2023/acs/acs5/subject/groups.json"

# Specific group variables
curl "https://api.census.gov/data/2023/acs/acs5/groups/B01003.json"
```

---

## Timeline Summary

```
Week 1: Phase 8 Start
├─ Day 1-2: Research + Setup
├─ Day 3-4: Build table index
└─ Day 5: Test retrieval

Week 2: Phase 8 Complete
├─ Day 1-2: Update retrieval pipeline
├─ Day 3-4: Integration testing
└─ Day 5: Validation + Documentation

Week 3: Phase 9 Start
├─ Day 1-2: Add multi-category config
├─ Day 3-4: Implement category selector
└─ Day 5: Update API utils

Week 4: Phase 9 Complete
├─ Day 1-2: Build multi-category index
├─ Day 3-4: End-to-end testing
└─ Day 5: Documentation + Deploy
```

**Total**: 4 weeks to production-ready, accurate system

---

## Final Checklist Before You Start

- [ ] Read `CENSUS_DISCUSSION.md` to understand Census API structure
- [ ] Review `ARCHITECTURE-REMEDIATION-ROADMAP.md` for full context
- [ ] Backup existing ChromaDB collection
- [ ] Create feature branch: `git checkout -b feature/table-architecture`
- [ ] Have `IMPLEMENTATION-TEMPLATES.md` open for copy-paste
- [ ] Set up test queries to validate improvements
- [ ] Schedule 4 weeks for full implementation
- [ ] Get stakeholder approval for timeline

---

## One-Page Summary

**Problem**: Wrong abstraction level + missing data categories = 53% accuracy

**Solution**: 
- Phase 8: Table-level search (2-3 weeks) → 67% accuracy
- Phase 9: Multi-category support (2-3 weeks) → 92% accuracy

**Key Changes**:
1. Search tables not variables
2. Add all 5 Census categories
3. Use Groups API
4. Build dynamic URLs

**Files to Create**: `census_groups_api.py`, `category_selector.py`, `build_index_tables.py`

**Files to Modify**: `config.py`, `retrieve.py`, `census_api_utils.py`, `types.py`

**Success**: Natural language queries work, all Census data accessible, 92%+ accuracy

---

**Document Version**: 1.0  
**Created**: October 9, 2025  
**Purpose**: Quick reference for Census Tool remediation  
**Start Here**: Then read full documents for details


