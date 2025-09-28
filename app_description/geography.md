## **COMPREHENSIVE PLAN: Dynamic Geography Resolution Architecture**

DO NOT CHANGE CODE YOURSELF UNLESS I SAY SO. I wanted to learn so I need your guidance.

## **PHASE 1: Architecture Redesign**

### **Current Problem Analysis**
Your current system has these fundamental limitations:
1. **Static dictionaries** can't handle 85,000 tracts, 3,143 counties, 50 states + territories
2. **Hardcoded mappings** fail for any location not explicitly listed
3. **No dynamic lookup** means users must know exact Census API codes
4. **Missing geocoding service** - no way to convert "Chicago" → place:14000, state:17

### **New Architecture Design**

```
User Query → Text Parser → Geography Resolver → Census API Filters
                ↓              ↓                    ↓
            Extract Geo    Dynamic Lookup    Build API URL
            Entities       via Census API    with FIPS codes
```

## **PHASE 2: Core Components to Build**

### **1. Text Parser Module** (`src/utils/geo_parser.py`)
**Purpose**: Extract geography entities and levels from natural language

```python
# Example structure
class GeographyParser:
    def parse_query(self, text: str) -> GeographyRequest:
        # Extract: geography_type, location_name, state_context, level_hint
        pass
    
    def extract_geography_entities(self, text: str) -> List[GeographyEntity]:
        # Use NLP to find: cities, counties, states, tracts
        pass
```

### **2. Census Geocoding Service** (`src/services/census_geocoding.py`)
**Purpose**: Dynamic lookup using Census Geocoding API

```python
# Example structure  
class CensusGeocodingService:
    def geocode_place(self, place_name: str, state: str = None) -> ResolvedGeography:
        # Call Census Geocoding API
        pass
    
    def geocode_county(self, county_name: str, state: str) -> ResolvedGeography:
        # Resolve county FIPS codes
        pass
    
    def validate_geography_level(self, level: str, location: str) -> bool:
        # Check if level is supported for this location
        pass
```

### **3. Enhanced Geography Resolver** (`src/utils/geo_resolver.py`)
**Purpose**: Orchestrate the dynamic resolution process

```python
# Example structure
class DynamicGeographyResolver:
    def resolve_geography(self, geo_request: GeographyRequest) -> ResolvedGeography:
        # 1. Parse the request
        # 2. Call appropriate geocoding service
        # 3. Validate against supported levels
        # 4. Return Census API filters
        pass
```

## **PHASE 3: Implementation Strategy**

### **Step 1: Create New Service Layer**
- **File**: `src/services/__init__.py` (new directory)
- **File**: `src/services/census_geocoding.py` 
- **File**: `src/services/geography_cache.py` (for performance)

### **Step 2: Enhance Text Parsing**
- **File**: `src/utils/geo_parser.py` (new)
- **Enhancement**: `src/utils/text_utils.py` - improve `extract_geo_hint()`

### **Step 3: Replace Static Resolution**
- **Replace**: `src/utils/geo_utils.py` - `resolve_geography_hint()`
- **New**: `src/utils/geo_resolver.py` - dynamic resolution logic

### **Step 4: Update Node Integration**
- **Update**: `src/nodes/geo.py` - integrate new resolver
- **Update**: `src/state/types.py` - new geography data structures

## **PHASE 4: Data Structures**

### **New Geography Data Models**

```python
class GeographyEntity(BaseModel):
    name: str = Field(..., description="Name of the geographic entity")
    type: str = Field(..., description="Type: 'city', 'county', 'state', 'tract'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context information")

class GeographyRequest(BaseModel):
    raw_text: str = Field(..., description="Original user query text")
    entities: List[GeographyEntity] = Field(default_factory=list, description="Extracted geography entities")
    requested_level: Optional[str] = Field(None, description="Requested geography level")
    state_context: Optional[str] = Field(None, description="State context if provided")

class ResolvedGeography(BaseModel):
    level: str = Field(..., description="Resolved geography level")
    filters: Dict[str, str] = Field(default_factory=dict, description="Census API filters")
    display_name: str = Field(..., description="Human-readable location name")
    fips_codes: Dict[str, str] = Field(default_factory=dict, description="FIPS codes for the location")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Resolution confidence score")
    note: str = Field(default="", description="Additional notes about the resolution")
```

## **PHASE 5: Census API Integration**

### **Available Census APIs to Use**

1. **Census Geocoding API** - Convert addresses/places to coordinates + FIPS
2. **Census Geography API** - Get geographic hierarchies and relationships  
3. **Census Data API** - Your existing integration (already working)

### **Key Endpoints**
```
# Geocoding API
https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress

# Geography API  
https://api.census.gov/data/2020/dec/geography
```

## **PHASE 6: Implementation Phases**

### **Phase 6A: Foundation (Week 1)**
1. Create service layer structure
2. Implement basic Census Geocoding API client
3. Create new data structures
4. Build basic text parser

### **Phase 6B: Core Resolution (Week 2)**  
1. Implement dynamic geography resolver
2. Add caching layer for performance
3. Handle error cases and fallbacks
4. Update geo_node integration

### **Phase 6C: Advanced Features (Week 3)**
1. Add county-level resolution
2. Implement state abbreviation handling
3. Add geography level validation
4. Performance optimization

### **Phase 6D: Testing & Integration (Week 4)**
1. Comprehensive testing suite
2. Integration with existing workflow
3. Performance benchmarking
4. Documentation updates

## **PHASE 7: Specific Implementation Details**

### **For Your Two Example Questions:**

**"What is the population of Chicago?"**
1. **Parser**: Extracts "Chicago" as city entity
2. **Geocoding**: Calls Census API → gets place:14000, state:17  
3. **Resolver**: Returns `{"for": "place:14000", "in": "state:17"}`
4. **Result**: Chicago city data (not Illinois state)

**"Can you give me the population of IL Cook County by census tract"**
1. **Parser**: Extracts "Cook County", "IL", "tract" level
2. **Geocoding**: Resolves Cook County → county:031, state:17
3. **Validation**: Detects "tract" is unsupported level
4. **Result**: Error with suggestion to use county-level instead

## **PHASE 8: Migration Strategy**

### **Backward Compatibility**
- Keep existing `GEOGRAPHY_MAPPINGS` as fallback
- Gradually migrate to dynamic resolution
- Maintain same output format for downstream nodes

### **Performance Considerations**
- Cache geocoding results (avoid repeated API calls)
- Batch geocoding requests when possible
- Implement rate limiting and retry logic

## **PHASE 9: Testing Strategy**

### **Unit Tests**
- Text parsing accuracy
- Geocoding API integration
- Error handling scenarios

### **Integration Tests**  
- End-to-end geography resolution
- Performance under load
- Cache effectiveness

### **User Acceptance Tests**
- Real-world geography queries
- Edge cases and ambiguous inputs
- Error message clarity

This plan transforms your static system into a dynamic, scalable geography resolution engine that can handle any US location while maintaining the existing workflow structure. The key is building the service layer first, then gradually replacing the static dictionaries with dynamic API calls.

Would you like me to start implementing any specific phase of this plan?

```plaintext
User Query → Text Parser → Geography Resolver → Census API Filters
                ↓              ↓                    ↓
            Extract Geo    Dynamic Lookup    Build API URL
            Entities       via Census API    with FIPS codes
```

```python
# Example structure
class GeographyParser:
    def parse_query(self, text: str) -> GeographyRequest:
        # Extract: geography_type, location_name, state_context, level_hint
        pass
    
    def extract_geography_entities(self, text: str) -> List[GeographyEntity]:
        # Use NLP to find: cities, counties, states, tracts
        pass
```

```python
# Example structure  
class CensusGeocodingService:
    def geocode_place(self, place_name: str, state: str = None) -> ResolvedGeography:
        # Call Census Geocoding API
        pass
    
    def geocode_county(self, county_name: str, state: str) -> ResolvedGeography:
        # Resolve county FIPS codes
        pass
    
    def validate_geography_level(self, level: str, location: str) -> bool:
        # Check if level is supported for this location
        pass
```

```python
# Example structure
class DynamicGeographyResolver:
    def resolve_geography(self, geo_request: GeographyRequest) -> ResolvedGeography:
        # 1. Parse the request
        # 2. Call appropriate geocoding service
        # 3. Validate against supported levels
        # 4. Return Census API filters
        pass
```

```python
@dataclass
class GeographyEntity:
    name: str
    type: str  # 'city', 'county', 'state', 'tract'
    confidence: float
    context: Dict[str, Any]

@dataclass
class GeographyRequest:
    raw_text: str
    entities: List[GeographyEntity]
    requested_level: Optional[str]
    state_context: Optional[str]

@dataclass
class ResolvedGeography:
    level: str
    filters: Dict[str, str]  # Census API filters
    display_name: str
    fips_codes: Dict[str, str]
    confidence: float
    note: str
```

```plaintext
# Geocoding API
https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress

# Geography API  
https://api.census.gov/data/2020/dec/geography
```

## **PHASE 10: Implementation Enhancements**

### **Missing Import Statements**
The data structures need proper imports:
```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
```

### **Error Handling Classes**
```python
class GeographyError(BaseModel):
    error_type: str = Field(..., description="Error type: 'unsupported_level', 'not_found', 'api_error'")
    message: str = Field(..., description="Human-readable error message")
    suggested_alternatives: List[str] = Field(default_factory=list, description="Suggested alternative locations or levels")
```

### **Configuration Constants**
Add to `config.py`:
```python
# Census Geocoding API Settings
CENSUS_GEOCODING_BASE_URL = "https://geocoding.geo.census.gov/geocoder"
GEOCODING_CACHE_TTL = 86400  # 24 hours
MAX_GEOCODING_RETRIES = 3
GEOCODING_TIMEOUT = 30  # seconds
```

### **Enhanced Data Structures**
```python
class GeographyEntity(BaseModel):
    name: str = Field(..., description="Name of the geographic entity")
    type: str = Field(..., description="Type: 'city', 'county', 'state', 'tract'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context information")
    start_pos: int = Field(..., ge=0, description="Start position in original text")
    end_pos: int = Field(..., ge=0, description="End position in original text")

class GeographyRequest(BaseModel):
    raw_text: str = Field(..., description="Original user query text")
    entities: List[GeographyEntity] = Field(default_factory=list, description="Extracted geography entities")
    requested_level: Optional[str] = Field(None, description="Requested geography level")
    state_context: Optional[str] = Field(None, description="State context if provided")
    user_id: Optional[str] = Field(None, description="User ID for caching")

class ResolvedGeography(BaseModel):
    level: str = Field(..., description="Resolved geography level")
    filters: Dict[str, str] = Field(default_factory=dict, description="Census API filters")
    display_name: str = Field(..., description="Human-readable location name")
    fips_codes: Dict[str, str] = Field(default_factory=dict, description="FIPS codes for the location")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Resolution confidence score")
    note: str = Field(default="", description="Additional notes about the resolution")
    geocoding_metadata: Dict[str, Any] = Field(default_factory=dict, description="API response details")
```

### **Service Layer Enhancements**
```python
# src/services/geography_cache.py
class GeographyCache:
    def __init__(self, ttl: int = GEOCODING_CACHE_TTL):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[ResolvedGeography]:
        # Check cache with TTL
        pass
    
    def set(self, key: str, value: ResolvedGeography):
        # Store with timestamp
        pass
```

### **Performance Optimizations**
1. **Batch Geocoding Requests** - Group multiple locations
2. **Async API Calls** - Use asyncio for concurrent requests
3. **Smart Caching** - Cache by user_id + location for personalization
4. **Fallback Chain** - Static mappings → Cache → API → Error

### **Testing Enhancements**
```python
# app_test_scripts/test_dynamic_geo.py
def test_chicago_resolution():
    """Test Chicago -> place:14000, state:17"""
    
def test_cook_county_tract_error():
    """Test Cook County tract -> unsupported level error"""
    
def test_geocoding_cache():
    """Test caching behavior"""
    
def test_fallback_to_static():
    """Test fallback when API fails"""
```
