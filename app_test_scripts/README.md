# Census Tool Test Suite

This directory contains all test files for the Census Tool application. The tests are organized to cover different components and functionality of the census data processing system.

## Test Files Overview

### Core Application Tests

#### `test_main_app.py` (7.5KB, 238 lines)
- **Purpose**: Tests the main application entry point and core functionality
- **Key Tests**:
  - Main app startup and initialization
  - Census app creation and graph compilation
  - State management and routing
  - Error handling and edge cases
- **Dependencies**: `main.py`, `app.py`, `src.state.types`

#### `test_app_integration.py` (260B, 14 lines)
- **Purpose**: High-level integration tests for the complete workflow
- **Key Tests**:
  - Graph creation and compilation
  - Workflow routing between nodes
  - State management across the entire pipeline
- **Status**: Placeholder tests (pass) - ready for implementation

### Node-Specific Tests

#### `test_intent.py` (2.5KB, 82 lines)
- **Purpose**: Tests the intent classification and parsing functionality
- **Key Tests**:
  - Census question detection
  - Intent parsing (measures, geography, time)
  - Clarification handling
- **Dependencies**: `src.nodes.intent`

#### `test_geo.py` (6.2KB, 185 lines)
- **Purpose**: Tests geographic data processing and location parsing
- **Key Tests**:
  - Geographic entity recognition
  - Location hierarchy processing
  - Geographic filters and constraints
- **Dependencies**: `src.nodes.geo`

#### `test_data.py` (7.0KB, 235 lines)
- **Purpose**: Tests data retrieval and processing from Census API
- **Key Tests**:
  - Census API integration
  - Data fetching and validation
  - Error handling for API failures
- **Dependencies**: `src.nodes.data`, `src.state.types`

#### `test_retrieve.py` (16KB, 441 lines)
- **Purpose**: Tests the retrieval system and ChromaDB integration
- **Key Tests**:
  - Document retrieval from vector database
  - Confidence scoring and ranking
  - Fallback candidate generation
  - Query processing and synonyms
- **Dependencies**: `src.nodes.retrieve`, `src.utils.retrieval_utils`, `src.utils.text_utils`

#### `test_plan.py` (11KB, 333 lines)
- **Purpose**: Tests the planning and query execution logic
- **Key Tests**:
  - Query planning and optimization
  - Execution strategy selection
  - State validation and error handling
- **Dependencies**: `src.nodes.retrieve.plan_node`, `src.state.types`

#### `test_memory.py` (1.5KB, 52 lines)
- **Purpose**: Tests memory management and persistence
- **Key Tests**:
  - Memory loading and saving
  - State persistence across sessions
- **Dependencies**: `src.nodes.memory`

### Utility and Display Tests

#### `test_memory_utils.py` (8.1KB, 231 lines)
- **Purpose**: Tests memory utility functions and caching
- **Key Tests**:
  - Cache management and retrieval
  - Memory optimization
  - Data persistence utilities
- **Dependencies**: `src.utils.memory_utils`

#### `test_displays.py` (6.8KB, 218 lines)
- **Purpose**: Tests result formatting and display functions
- **Key Tests**:
  - Result formatting and presentation
  - Single value and table displays
  - Error message formatting
- **Dependencies**: `src.utils.displays`

### Performance and End-to-End Tests

#### `test_cache_performance.py` (292B, 15 lines)
- **Purpose**: Performance testing for caching mechanisms
- **Key Tests**:
  - Cache hit performance benchmarks
  - Cache eviction policies
  - 90-day retention policy enforcement
- **Status**: Placeholder tests (pass) - ready for implementation

#### `test_e2e_workflows.py` (629B, 29 lines)
- **Purpose**: End-to-end workflow testing
- **Key Tests**:
  - Complete user query workflows
  - Population queries for NYC
  - Income trend analysis
  - County comparison tables
  - Non-census question handling
  - Ambiguous question clarification
  - API error handling and retries
- **Status**: Placeholder tests (pass) - ready for implementation

## Running Tests

### Run All Tests
```bash
python -m pytest app_test_scripts/ -v
```

### Run Specific Test File
```bash
python -m pytest app_test_scripts/test_retrieve.py -v
```

### Run Tests with Coverage
```bash
python -m pytest app_test_scripts/ --cov=src --cov-report=html
```

### Run Tests in Parallel
```bash
python -m pytest app_test_scripts/ -n auto
```

## Test Organization

### Import Patterns
The test files use two main import patterns:

1. **Direct Imports** (most files):
   ```python
   from src.nodes.retrieve import retrieve_node
   from src.utils.retrieval_utils import process_chroma_results
   ```

2. **Path Manipulation** (some files):
   ```python
   import sys
   import os
   sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   ```

### Test Structure
- Each test file focuses on a specific component or functionality
- Tests include both assertions and print statements for debugging
- Mock objects are used for external dependencies (APIs, databases)
- Tests are designed to work in CI/CD environments (GitHub Actions)

## Configuration

### pytest Configuration
The tests are configured to work with the project's `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["app_test_scripts"]
pythonpath = ["."]
```

### Test Data
- Tests use mock data and temporary files
- No external API calls during testing (mocked)
- ChromaDB uses in-memory or temporary instances

## Development Guidelines

### Adding New Tests
1. Create test files following the naming convention: `test_*.py`
2. Use descriptive test function names: `test_function_name_scenario()`
3. Include both assertions and print statements for debugging
4. Mock external dependencies
5. Add docstrings explaining test purpose

### Test Categories
- **Unit Tests**: Individual function/class testing
- **Integration Tests**: Component interaction testing
- **End-to-End Tests**: Complete workflow testing
- **Performance Tests**: Speed and resource usage testing

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure `src` directory is in Python path
2. **Missing Dependencies**: Check that all required packages are installed
3. **ChromaDB Issues**: Tests use temporary/mock ChromaDB instances
4. **API Mocking**: External APIs are mocked to prevent real calls

### Debug Mode
Run tests with verbose output and print statements:
```bash
python -m pytest app_test_scripts/ -v -s
```

## Pending Development Scripts

The following test files contain placeholder functions that need implementation:

### `test_app_integration.py` (260B, 14 lines)
- **Status**: 🔴 **PENDING** - All functions are placeholders
- **Missing Tests**:
  - `test_create_census_graph()` - Test graph creation and compilation
  - `test_workflow_routing()` - Test routing between nodes  
  - `test_state_management()` - Test state passing between nodes
- **Priority**: **HIGH** - Core integration functionality
- **Estimated Effort**: 2-3 hours

### `test_e2e_workflows.py` (629B, 29 lines)
- **Status**: 🔴 **PENDING** - All functions are placeholders
- **Missing Tests**:
  - `test_population_query_nyc()` - Test: 'What's the population of NYC in 2023?'
  - `test_income_trends_series()` - Test: 'Show me median income trends 2015-2020'
  - `test_county_comparison_table()` - Test: 'Compare population by county in California'
  - `test_non_census_question()` - Test: 'What's 2+2?' (should route to not_census)
  - `test_ambiguous_question()` - Test: 'Population data' (should trigger clarification)
  - `test_api_error_handling()` - Test: Network errors and retries
- **Priority**: **HIGH** - End-to-end user scenarios
- **Estimated Effort**: 4-6 hours

### `test_cache_performance.py` (292B, 15 lines)
- **Status**: 🔴 **PENDING** - All functions are placeholders
- **Missing Tests**:
  - `test_cache_hit_performance()` - Test cache hit speeds
  - `test_cache_eviction()` - Test cache size limits and eviction
  - `test_retention_policy_enforcement()` - Test 90-day retention policy
- **Priority**: **MEDIUM** - Performance optimization
- **Estimated Effort**: 2-3 hours

## Implementation Roadmap

### Phase 1: Core Integration (Priority: HIGH)
1. **test_app_integration.py** - Implement graph creation and workflow tests
2. **test_e2e_workflows.py** - Implement complete user scenario tests

### Phase 2: Performance Testing (Priority: MEDIUM)
3. **test_cache_performance.py** - Implement caching performance benchmarks

### Development Guidelines for Pending Scripts

#### For Integration Tests (`test_app_integration.py`)
```python
def test_create_census_graph():
    """Test graph creation and compilation"""
    # TODO: Test that create_census_graph() returns a valid graph
    # TODO: Verify all nodes are properly connected
    # TODO: Test graph compilation succeeds
    pass
```

#### For End-to-End Tests (`test_e2e_workflows.py`)
```python
def test_population_query_nyc():
    """Test: 'What's the population of NYC in 2023?'"""
    # TODO: Create test state with NYC population query
    # TODO: Run through complete workflow
    # TODO: Verify correct population data returned
    # TODO: Check result formatting
    pass
```

#### For Performance Tests (`test_cache_performance.py`)
```python
def test_cache_hit_performance():
    """Test cache hit speeds"""
    # TODO: Measure cache hit response times
    # TODO: Benchmark against cache miss times
    # TODO: Verify performance meets requirements
    pass
```

## Status Summary

- **Fully Implemented**: 9 test files with comprehensive test coverage
- **Pending Development**: 3 test files with placeholder functions
- **Total Test Files**: 12
- **Total Lines**: ~2,000+ lines of test code
- **Coverage**: Core application, all nodes, utilities, and workflows
- **Development Needed**: ~8-12 hours of additional test implementation
