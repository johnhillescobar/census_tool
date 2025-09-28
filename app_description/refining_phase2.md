# **PHASE 2 REFINEMENTS: Entity Recognition & State Context Issues**

## **🔍 DISCOVERED ISSUES DURING PHASE 6C TESTING**

### **Issue 1: spaCy Entity Label Inconsistency**

**Problem**: spaCy inconsistently labels geographic entities
- `"New York City"` → `GPE` ✅ (works)
- `"Rochester NY"` → `ORG` ❌ (filtered out)
- `"Rochester MN"` → `ORG` ❌ (filtered out)

**Current Filter**: Only accepts `["GPE", "LOC", "FAC"]` - missing `"ORG"`

**Impact**: Valid place names with state abbreviations get rejected

---

### **Issue 2: Entity Splitting & State Context Loss**

**Problem**: Complex location strings get split incorrectly
- Input: `"Houston, TX"`
- spaCy Output: `[('Houston', 'GPE'), ('TX', 'ORG')]`
- Result: "TX" gets filtered out, loses state context

**Impact**: State information is lost, causing geocoding in wrong states

---

### **Issue 3: State Context Resolution Bug**

**Problem**: State context extraction failing
- Input: `"Houston, TX"`
- Expected State: "Texas"
- Actual Result: "Alabama" (unknown why)
- Error: `"No matches found for 'Houston' in Alabama"`

**Impact**: Searches in completely wrong states

---

## **🎯 REQUIRED ENHANCEMENTS FOR END-TO-END TESTING**

### **Enhancement 1: Expand Entity Label Acceptance**
- Add `"ORG"` to accepted entity labels in `geo_parser.py`
- Create logic to validate if ORG entities are geographic

### **Enhancement 2: Improve State Context Extraction**
- Debug why "TX" → "Alabama" mapping occurs
- Enhance state abbreviation handling for ORG-labeled entities
- Add fallback patterns for state detection

### **Enhancement 3: Better Text Preprocessing**
- Consider preprocessing "City, State" patterns before spaCy
- Handle common geographic formats more robustly
- Improve entity consolidation logic

### **Enhancement 4: Comprehensive Testing Suite**
Create test cases for:
- State abbreviations: "Houston, TX", "Chicago, IL"
- Various formats: "Rochester NY", "Rochester, NY"  
- Edge cases: "St. Louis, MO", "Las Vegas, NV"
- Complex names: "New York, NY", "Kansas City, MO"

---

## **🚧 DEFERRAL REASONING**

These issues are **parser-level refinements** that should be addressed during comprehensive end-to-end testing phase. They don't block core architecture development but are critical for production accuracy.

**Current Priority**: Complete Phase 6C (county resolution, validation) before tackling entity recognition edge cases.

---

## **📋 TESTING CHECKLIST FOR FUTURE**

- [ ] Test all 50 state abbreviations with major cities
- [ ] Test various punctuation patterns (comma, no comma)
- [ ] Test county formats ("Cook County, IL")
- [ ] Benchmark entity recognition accuracy
- [ ] Add comprehensive parser test suite
