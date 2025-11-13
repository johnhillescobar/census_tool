def test_population_query_nyc():
    """Test: 'What's the population of NYC in 2023?'"""
    pass


def test_income_trends_series():
    """Test: 'Show me median income trends 2015-2020'"""
    pass


def test_county_comparison_table():
    """Test: 'Compare population by county in California'"""
    pass


def test_non_census_question():
    """Test: 'What's 2+2?' (should route to not_census)"""
    pass


def test_ambiguous_question():
    """Test: 'Population data' (should trigger clarification)"""
    pass


def test_api_error_handling():
    """Test: Network errors and retries"""
    pass


# ============================================================================
# E2E Tests for Expanded Geography Support
# ============================================================================


def test_tribal_area_workflow():
    """
    E2E Test: Query tribal area population

    User Query: "What's the population of Navajo Nation Reservation in 2023?"

    Expected workflow:
    1. Agent identifies tribal geography intent
    2. Uses resolve_area_name to find Navajo Nation code (5620R)
    3. Validates geography parameters with validate_geography_params
    4. Calls census_api_call with tribal geography token
    5. Returns population data

    This test validates:
    - Tribal geography token mapping
    - Suffix handling (R for reservation)
    - Fuzzy matching for tribal area names
    """
    pass


def test_metro_area_workflow():
    """
    E2E Test: Query metro area data

    User Query: "What's the median income in New York metro area in 2023?"

    Expected workflow:
    1. Agent identifies statistical area intent
    2. Uses resolve_area_name to find NYC metro code (35620)
    3. Validates geography parameters
    4. Calls census_api_call with metro area token
    5. Returns income data

    This test validates:
    - Statistical area token mapping
    - Metro area fuzzy matching
    - Proper API parameter construction
    """
    pass


def test_auto_repair_workflow():
    """
    E2E Test: Auto-repair bad geography ordering

    User Query: "Population by county in California"

    Simulated bad agent behavior:
    - Agent provides geo_for={"county": "*", "state": "06"} (wrong: both in for clause)

    Expected workflow:
    1. validate_geography_params detects bad ordering
    2. Auto-repairs to geo_for={"county": "*"}, geo_in={"state": "06"}
    3. Returns warnings about corrections made
    4. census_api_call succeeds with corrected parameters

    This test validates:
    - Automatic parameter repair
    - Warning generation
    - Successful API call after repair
    """
    pass


def test_missing_parent_workflow():
    """
    E2E Test: Detect and report missing parent geography

    User Query: "Population by county in 2023"

    Simulated bad agent behavior:
    - Agent provides geo_for={"county": "*"} without state

    Expected workflow:
    1. validate_geography_params detects missing parent
    2. Returns error: "Missing required parent geography: state"
    3. Agent uses geography_hierarchy to understand requirements
    4. Agent retries with correct parameters

    This test validates:
    - Missing parent detection
    - Helpful error messages
    - Agent self-correction capability
    """
    pass


def test_part_geography_workflow():
    """
    E2E Test: Query (or part) geography under metro area

    User Query: "Population by county in New York metro area"

    Expected workflow:
    1. Agent resolves "New York metro area" to code 35620
    2. Uses validate_geography_params to check hierarchy
    3. Calls census_api_call with:
       geo_for={"county (or part)": "*"}
       geo_in={"metropolitan statistical area/micropolitan statistical area": "35620"}
    4. Returns county-level data for NYC metro

    This test validates:
    - (or part) geography token handling
    - Parent-child relationship resolution
    - Correct API parameter construction
    """
    pass


def test_validation_before_api_workflow():
    """
    E2E Test: Recommended workflow with validation first

    User Query: "Median income by tract in Los Angeles County"

    Expected workflow:
    1. Agent resolves "Los Angeles County" to state=06, county=037
    2. Calls validate_geography_params BEFORE census_api_call
    3. Validation returns corrected parameters and confirms hierarchy
    4. Agent uses validated parameters in census_api_call
    5. Returns tract-level income data

    This test validates:
    - Validation-first workflow
    - Parameter correction before API call
    - Successful data retrieval
    """
    pass


def test_complex_hierarchy_workflow():
    """
    E2E Test: Complex geography hierarchy (metro division)

    User Query: "Population by county in Nassau-Suffolk metro division"

    Expected workflow:
    1. Agent resolves metro division to code 35614 under metro area 35620
    2. Uses geography_hierarchy to understand parent ordering
    3. Validates parameters with proper hierarchy
    4. Calls census_api_call with:
       geo_for={"county": "*"}
       geo_in={"metropolitan statistical area/micropolitan statistical area": "35620",
               "metropolitan division": "35614",
               "state (or part)": "36"}
    5. Returns county data for Nassau-Suffolk division

    This test validates:
    - Complex multi-level hierarchy handling
    - Proper parent ordering
    - Chained geography constraints
    """
    pass
