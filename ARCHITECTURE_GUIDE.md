# Architecture Guide for New Programmers

**Purpose**: This document provides new programmers with essential knowledge about the Census Tool architecture, coding patterns, and required skills to successfully contribute to this project.

**Last Updated**: Based on codebase review as of current date

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Architectural Patterns](#key-architectural-patterns)
3. [Coding Conventions](#coding-conventions)
4. [Required Skills](#required-skills)
5. [What New Programmers Must Know](#what-new-programmers-must-know)
6. [Common Pitfalls to Avoid](#common-pitfalls-to-avoid)

---

## Architecture Overview

### Core Design Philosophy

**Agent-First Architecture**: This project uses an **agent-first architecture** where a reasoning agent (CensusQueryAgent) handles complex multi-step queries internally, rather than a deterministic pipeline of nodes.
**Reasoning-Node-First Deterministic Principle**: Deterministic contracts and workflow/service steps are reliability scaffolding that empower AI reasoning nodes/components and must not replace AI reasoning nodes/components. Temporal/benchmark/comparison nodes clarify and gate ambiguous input early, while the reasoning node remains the execution owner, performs repeated strict typed Census tool calls as needed, and drives answer/table/chart directives.

**Key Principle**: 
```
User Question → Agent Reasons (multi-step) → Tools Execute → Agent Validates → Output Tools → Result
```

**NOT**: `User Question → Node1 → Node2 → Node3 → Done` (old deterministic approach)

### System Flow

The application uses a **branching workflow** defined in `app.py` (deterministic gating plus agent):

```
memory_load → temporal → benchmark → comparison → agent → comparison_metrics → output → memory_write
```

(with conditional edges to `output` when `plan.requires_clarification` is set)

1. **memory_load**: Loads user profile and conversation history from SQLite checkpoints
2. **temporal / benchmark / comparison**: Normalize and gate time-series, benchmark, and comparison intent into `plan`
3. **agent**: Calls CensusQueryAgent which reasons through the query using registered tools
4. **comparison_metrics**: Computes comparison metrics when that path is taken
5. **output**: Generates charts/tables from agent results using output tools
6. **memory_write**: Saves conversation state back to SQLite

### Component Hierarchy

```
app.py (LangGraph workflow)
  └── src/workflows/
      ├── memory.py (memory_load_node, memory_write_node)
      ├── temporal.py, benchmark.py, comparison.py, comparison_metrics.py
      ├── agent.py (agent_reasoning_node)
      └── output.py (output_node)
          └── src/agents/census_query_agent.py (CensusQueryAgent)
              └── src/tools/ (see self.tools in census_query_agent.py)
```

---

## Key Architectural Patterns

### 1. Agent Pattern (ReAct)

**Location**: `src/agents/census_query_agent.py`

The CensusQueryAgent uses the **ReAct pattern** (Reasoning + Acting):
- Agent reasons about what to do next
- Agent calls tools to gather information
- Agent validates results and decides next steps
- Agent repeats until it has the answer

**Key Characteristics**:
- Multi-step reasoning (up to 30 iterations)
- Tool-based execution (tools listed in `CensusQueryAgent.__init__`)
- Structured output format (census_data, answer_text, charts_needed, tables_needed)
- Error recovery and fallback handling

**Example Flow**:
```
User: "Population of NYC"
Agent: Thought: Need to resolve "NYC" → Action: area_resolution_tool
Tool: Returns FIPS code for New York City
Agent: Thought: Need population data → Action: table_search_tool
Tool: Returns B01003_001E (Total Population)
Agent: Thought: Fetch data → Action: census_api_tool
Tool: Returns population data
Agent: Final Answer: "8,258,035 people"
```

### 2. Tool Pattern (LangChain BaseTool)

**Location**: `src/tools/*.py`

All tools inherit from `langchain_core.tools.BaseTool` and follow this structure:

```python
class MyTool(BaseTool):
    name: str = "tool_name"
    description: str = "Clear description of what the tool does"
    
    def _run(self, param1: str, param2: int = None) -> Dict[str, Any]:
        # Tool implementation
        logger.info(f"Running {self.name} with params...")
        # ... tool logic ...
        return {"result": "data"}
```

**Key Requirements**:
- Must have `name` and `description` (used by agent to decide when to call)
- Must implement `_run()` method
- Should use structured logging (`logger.info/error/warning`)
- Should return structured data (dicts, not strings)
- Should handle errors gracefully

**Tool Registration**: Tools are registered in `CensusQueryAgent.__init__()`:
```python
self.tools = [
    GeographyDiscoveryTool(),
    AreaResolutionTool(),
    TableSearchTool(),
    # ... etc
]
```

### 3. State Management Pattern (TypedDict)

**Location**: `src/state/types.py`

The workflow uses a **TypedDict** (`CensusState`) for state management:

```python
class CensusState(BaseModel):
    messages: List[Dict[str, Any]]  # Chat history
    artifacts: Dict[str, Any]       # Agent results (census_data, reasoning_trace)
    final: Dict[str, Any]           # Output specs (charts_needed, answer_text)
    profile: Dict[str, Any]         # User preferences
    # ... more fields
```

**State Reducers**: Defined in `app.py` - specify how state merges:
- `append_reducer`: For lists (messages, logs, history)
- `overwrite_reducer`: For single values (intent, geo, plan)
- `merge_reducer`: For dictionaries (artifacts, profile, cache_index)

**Key Rule**: Nodes return partial state dictionaries that get merged using reducers.

### 4. Node Pattern (LangGraph Nodes)

**Location**: `src/workflows/*.py`

Nodes are functions that take `CensusState` and `RunnableConfig`, return partial state:

```python
def my_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    # Read from state
    user_question = state.messages[-1]["content"]
    
    # Do work
    result = some_processing(user_question)
    
    # Return partial state update
    return {
        "artifacts": {"my_data": result},
        "logs": ["my_node: completed"]
    }
```

**Key Requirements**:
- Must accept `CensusState` and `RunnableConfig`
- Must return dict with state field updates
- Should use logging (`logger.info/error`)
- Should handle errors gracefully (don't crash the graph)

### 5. LLM Factory Pattern

**Location**: `src/llm/factory.py`

Centralized LLM creation supporting multiple providers (OpenAI, Anthropic, Google):

```python
llm = create_llm(temperature=0.1)  # Uses config from src/llm/config.py
```

**Key Features**:
- Provider abstraction (switch providers via config)
- API compatibility handling (GPT-5 Responses API vs Chat Completions)
- Fallback support (`create_llm_with_fallback()`)
- Automatic API key detection from environment

**Configuration**: `src/llm/config.py` - single source of truth for LLM settings

### 6. Caching Pattern

**Location**: `src/clients/file_utils.py`, `src/services/memory_utils.py`, `config.py`

**Retention Policy**:
- 90-day retention (`RETENTION_DAYS = 90`)
- LRU eviction when limits exceeded
- Size limits: `CACHE_MAX_FILES = 2000`, `CACHE_MAX_BYTES = 2GB`

**Cache Structure**:
- Files stored in `data/` directory
- Naming: `{variable}_{level}_{year}.csv`
- Indexed in `state.cache_index` for fast lookup

### 7. Error Handling Pattern

**Consistent Approach**:
- Use try/except blocks with specific exception types
- Log errors with context (`logger.error(f"Failed to X: {e}")`)
- Provide fallback behavior when possible
- Never crash the graph - return error in state instead

**Example**:
```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    result = fallback_operation()  # Graceful degradation
```

### 8. Logging Pattern

**Standard Setup**:
- Module-level logger: `logger = logging.getLogger(__name__)`
- Structured logging: Include context in messages
- Log levels: DEBUG (detailed), INFO (operations), WARNING (recoverable issues), ERROR (failures)

**Example**:
```python
logger.info(f"Running {tool_name} with query: {query}")
logger.debug(f"Tool returned {len(results)} results")
logger.warning(f"Low confidence score: {score}")
logger.error(f"API call failed: {e}", exc_info=True)
```

---

## Coding Conventions

### File Organization

```
src/
├── workflows/      # LangGraph nodes: memory, temporal, benchmark, comparison, agent, comparison_metrics, output
├── domain/         # Geography registry, Pydantic contracts, time/text/geo helpers
├── clients/        # Census API, Chroma, files, PDF, telemetry, session logging
├── services/       # Validators, policies, memory, footnotes, dataframes, summarizer
├── agents/         # CensusQueryAgent
├── tools/          # BaseTool implementations (registered in census_query_agent)
├── api/            # Presentation helpers (e.g. displays)
├── state/          # CensusState and typing
├── llm/            # Factory, config, intent/category/geo helpers
└── locations/      # Reference CSVs (states, counties)
```

Top-level folders commonly touched: `app_test_scripts/` (tests), `index/` (builders), `app_description/` + `docs/` (specs), `data/` / `chroma/` / `memory/` / `logs/` (runtime).

### Import Patterns

**Standard Import Order**:
1. Standard library (`os`, `logging`)
2. Third-party (`langchain_core`, `pandas`)
3. Local imports (`from src...`)

**Path Setup**:
- Do not use `sys.path.append()` hacks.
- Use package imports from project root (e.g., `from src.tools...`) and run via `uv run ...`.

### Naming Conventions

- **Classes**: PascalCase (`CensusQueryAgent`, `TableSearchTool`)
- **Functions**: snake_case (`agent_reasoning_node`, `create_llm`)
- **Constants**: UPPER_SNAKE_CASE (`RETENTION_DAYS`, `CENSUS_API_TIMEOUT`)
- **Files**: snake_case (`census_query_agent.py`, `table_search_tool.py`)

### Type Hints

**Required**: Use type hints for function parameters and returns:
```python
def my_function(param1: str, param2: int = None) -> Dict[str, Any]:
    ...
```

**State Types**: Use `CensusState` from `src.state.types`:
```python
from src.state.types import CensusState
def my_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    ...
```

### Documentation

**Docstrings**: Use Google-style docstrings for classes and functions:
```python
def my_function(param1: str, param2: int = None) -> Dict[str, Any]:
    """
    Brief description.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional)
    
    Returns:
        Dict with keys: result, status
    
    Raises:
        ValueError: If param1 is invalid
    """
```

### Testing Patterns

**Test Location**: `app_test_scripts/test_*.py`

**Test Structure**:
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

**Example**:
```python
def test_my_feature():
    """Test description"""
    # Arrange
    input_data = {...}
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result["status"] == "success"
```

**Run Tests**:
```bash
uv run pytest app_test_scripts/test_*.py -v
```

---

## Required Skills

### Essential Skills (Must Have)

1. **Python 3.12+**
   - Type hints (`typing` module)
   - Dataclasses and Pydantic models
   - Async/await (basic understanding)
   - Context managers

2. **LangChain & LangGraph**
   - LangChain tool creation (`BaseTool`)
   - LangGraph node creation
   - State management with TypedDict
   - Agent patterns (ReAct)

3. **Object-Oriented Programming**
   - Class inheritance
   - Method overriding
   - Design patterns (Factory, Strategy)

4. **API Integration**
   - REST API calls (`requests` library)
   - Error handling and retries
   - Rate limiting awareness

5. **Data Structures**
   - Dictionaries (extensive use)
   - Lists and list comprehensions
   - Pandas DataFrames (basic operations)

6. **Testing**
   - pytest framework
   - Test organization and fixtures
   - Assertion patterns

### Intermediate Skills (Should Have)

1. **Vector Databases**
   - ChromaDB basics (collections, queries)
   - Embeddings and semantic search
   - Vector similarity concepts

2. **LLM Integration**
   - Prompt engineering
   - Token limits and context windows
   - Provider-specific APIs (OpenAI, Anthropic, Google)

3. **Data Visualization**
   - Plotly basics (charts, layouts)
   - Chart type selection (bar, line, scatter)

4. **SQLite**
   - Basic queries
   - Connection management
   - Checkpointing patterns

5. **Logging & Debugging**
   - Python logging module
   - Debugging techniques
   - Error traceback analysis

### Advanced Skills (Nice to Have)

1. **Census API Knowledge**
   - ACS datasets and variables
   - Geography hierarchies (state → county → place)
   - FIPS codes and geography patterns

2. **Performance Optimization**
   - Caching strategies
   - Parallel processing (`asyncio`, `concurrent.futures`)
   - Memory management

3. **Streamlit**
   - Web interface development
   - State management
   - Component usage

---

## What New Programmers Must Know

### 1. Entry Points

**CLI**: `main.py` - Command-line interface
**Web**: `streamlit_app.py` - Streamlit web interface
**Launcher**: `launcher.py` - Choose between CLI/Web

**Graph Definition**: `app.py` - Creates LangGraph workflow

### 2. Configuration Files

**`config.py`**: Application settings (retention, API limits, performance)
**`src/llm/config.py`**: LLM provider and model configuration
**`pyproject.toml`**: Dependencies (managed by `uv`)

### 3. Key Files to Understand

**Before Making Changes**:
1. `app.py` - Graph structure
2. `src/agents/census_query_agent.py` - Agent implementation
3. `src/state/types.py` - State schema
4. `src/workflows/agent.py` - Agent node (calls CensusQueryAgent)
5. `src/workflows/output.py` - Output generation

**When Adding Tools**:
1. `src/tools/` - See existing tool examples
2. `src/agents/census_query_agent.py` - Register tool here

**When Modifying State**:
1. `src/state/types.py` - Update CensusState
2. `app.py` - Validate graph state flow and integration points

### 4. Testing Requirements

**Before Committing**:
- Run existing tests: `uv run pytest app_test_scripts/ -v`
- Add tests for new functionality
- Ensure all tests pass

**Test Coverage Areas**:
- Unit tests for tools (`test_*_tool.py`)
- Integration tests for nodes (`test_main_app.py`)
- End-to-end workflow tests (`test_e2e_workflows.py`)

### 5. Common Workflows

**Adding a New Tool**:
1. Create `src/tools/my_tool.py` inheriting from `BaseTool`
2. Implement `_run()` method
3. Register in `CensusQueryAgent.__init__()` tools list
4. Update agent prompt if needed (`src/llm/config.py`)
5. Add tests in `app_test_scripts/test_my_tool.py`

**Modifying Agent Behavior**:
1. Edit `src/agents/census_query_agent.py`
2. Update prompt template in `src/llm/config.py` (if needed)
3. Test with `test_census_query_agent.py`
4. Run integration tests

**Changing Graph Structure**:
1. Edit `app.py` (add/remove nodes, edges)
2. Update node implementations in `src/workflows/`
3. Update state contracts if state structure changes
4. Test graph compilation: `create_census_graph()` should succeed
5. Run full test suite

### 6. Environment Setup

**Required Environment Variables**:
```bash
OPENAI_API_KEY=sk-...          # For OpenAI models
ANTHROPIC_API_KEY=sk-ant-...  # For Claude models
GOOGLE_API_KEY=AIza...        # For Gemini models
```

**Optional**:
```bash
LANGCHAIN_TRACING_V2=true     # LangSmith tracing
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=census-tool
```

**Setup Steps**:
1. Install dependencies: `uv sync`
2. Build index: `uv run python index/build_index.py`
3. Run tests: `uv run pytest app_test_scripts/ -v`

### 7. Code Review Checklist

Before submitting code:
- [ ] Follows existing patterns (tools inherit BaseTool, nodes return partial state)
- [ ] Includes type hints
- [ ] Has docstrings for public functions
- [ ] Uses logging appropriately
- [ ] Handles errors gracefully
- [ ] Includes tests
- [ ] All tests pass
- [ ] No hardcoded values (use config.py)
- [ ] No breaking changes to state schema (or updates reducers)

---

## Common Pitfalls to Avoid

### 1. Breaking State Schema

**Problem**: Modifying `CensusState` without updating workflow/state consumers
**Solution**: Update `src/workflows/*`, `app.py`, and tests when changing state fields

### 2. Tool Registration

**Problem**: Creating a tool but forgetting to register it in CensusQueryAgent
**Solution**: Add tool to `self.tools` list in `CensusQueryAgent.__init__()`

### 3. State Updates

**Problem**: Returning full state instead of partial updates
**Solution**: Nodes should return only changed fields: `{"artifacts": {...}}`, not full state

### 4. Error Handling

**Problem**: Letting exceptions crash the graph
**Solution**: Catch exceptions, log them, return error in state or use fallback

### 5. Logging Context

**Problem**: Logging without context makes debugging hard
**Solution**: Include relevant data: `logger.info(f"Processing query: {query} for user: {user_id}")`

### 6. Testing Isolation

**Problem**: Tests that depend on external APIs or specific data
**Solution**: Mock external calls, use fixtures for test data

### 7. Hardcoded Values

**Problem**: Magic numbers/strings in code
**Solution**: Move to `config.py` or constants at module level

### 8. Import Paths

**Problem**: Relative imports failing
**Solution**: Keep absolute package imports (`from src...`) and run commands from project root using `uv run`.

### 9. LLM Provider Assumptions

**Problem**: Assuming OpenAI-specific behavior
**Solution**: Use `create_llm()` factory, test with multiple providers

### 10. State Reducer Mismatch

**Problem**: Using `append_reducer` for dict or `merge_reducer` for list
**Solution**: Match reducer to data type: lists → append, dicts → merge, single values → overwrite

---

## Additional Resources

### Documentation Files

- **`README.md`**: User-facing documentation
- **`USAGE_GUIDE.md`**: How to use the application
- **`app_description/ARCHITECTURE.md`**: Detailed architecture specification

### Key Directories

- **`app_test_scripts/`**: All test files
- **`src/tools/`**: Agent tools (study these for patterns)
- **`src/domain/`, `src/clients/`, `src/services/`**: Core layered modules
- **`src/workflows/`**: LangGraph nodes (`memory`, `temporal`, `benchmark`, `comparison`, `agent`, `comparison_metrics`, `output` — see `app.py`)
- **`src/agents/`**: Agent implementation
- **`index/`**: Index building scripts (`build_index.py`, `build_geography_index.py`, etc.)
- **`docs/`**, **`app_description/`**: Architecture and contract documentation
- **`data/`**, **`chroma/`**, **`memory/`**, **`logs/`**: Runtime outputs and local persistence

### Learning Path

1. **Start**: Read `README.md` and `ARCHITECTURE.md`
2. **Explore**: Run the app (`uv run python main.py`)
3. **Study**: Look at existing tools (`src/tools/table_search_tool.py`)
4. **Practice**: Write a simple test (`app_test_scripts/test_my_feature.py`)
5. **Contribute**: Add a small feature following existing patterns

---

## Summary

**Core Architecture**: Agent-first with gating nodes plus agent/output/memory (see `app.py`)
**Key Pattern**: Tools → Agent → Output
**State Management**: TypedDict with reducers
**Testing**: pytest with integration tests
**Skills Needed**: Python, LangChain, OOP, APIs, Testing

**Golden Rule**: Follow existing patterns. When in doubt, look at similar code in the codebase.

---

*This guide is a living document. Update it when architecture changes significantly.*
