# Census Tool

A sophisticated local Census QA application that answers questions about US Census data using LangGraph, ChromaDB, and the Census API. This tool uses an **agent-first architecture** with multi-step reasoning to handle complex Census API queries, providing intelligent query processing, semantic variable retrieval, and comprehensive data caching with conversation memory.

## Reasoning-Node-First Principle

Canonical principle: deterministic contracts and workflow/service steps are reliability scaffolding that empower AI reasoning nodes/components and must not replace AI reasoning nodes/components.

### Architecture Invariant (Non-Negotiable)

- Pydantic typed contracts must prevent malformed objects at the earliest boundary (from the start), before reasoning execution.
- Deterministic gates (temporal/benchmark/comparison and related services) must normalize, clarify, and hand off typed artifacts.
- The reasoning node is not the primary contract-validation owner; it translates gated user intent into Census tool parameters, executes tool loops, analyzes generated artifacts, and produces human answer/table/chart outputs.
- Deterministic scaffolding exists to improve reasoning-node reliability and traceability, not to bypass or replace reasoning-node ownership.

- Temporal/benchmark/comparison planning nodes clarify and gate ambiguous input early.
- The reasoning node remains the execution owner, performs repeated strict typed Census tool calls as needed, and drives answer/table/chart directives.
- Architecture changes must preserve reasoning-node ownership while improving reliability, traceability, and fail-closed behavior.

> **📋 Technical Documentation**: For detailed architecture information, see **[ARCHITECTURE.md](app_description/ARCHITECTURE.md)** - the single source of truth for the agent-first implementation.

## 🚀 Features

### Core Functionality
- **Agent-Based Reasoning** - Multi-step reasoning agent that handles complex Census API queries using specialized tools
- **Geography Discovery** - Dynamic geography enumeration and pattern building for 144+ Census API patterns
- **Table Search & Validation** - ChromaDB-based semantic search with table-geography compatibility validation
- **Census API Integration** - Robust API calls with support for all data categories (Detail, Subject, Profile, Comparison, SPP)
- **Output Generation** - Automatic chart and table generation with formatted answers and proper footnotes
- **Memory Management** - User profiles, conversation history, and intelligent caching with retention policies

### Advanced Capabilities
- **Conversation Memory** - Maintains thread state and user preferences across sessions
- **Intelligent Caching** - 90-day retention with LRU eviction and size limits
- **Parallel Processing** - Concurrent API calls for multi-year data requests
- **Error Handling** - Graceful degradation with fallback responses and clarification prompts
- **Message Summarization** - Automatic conversation trimming to maintain performance

## 📋 Project Status

**Current Status**: ✅ **FULLY OPERATIONAL** - All core features working and tested

### Verified Working Components
- ✅ **Agent-First Architecture** - LangGraph workflow in `app.py`: `memory_load` → `temporal` → `benchmark` → `comparison` → `agent` → `comparison_metrics` → `output` → `memory_write` (with conditional edges to `output` for clarification)
- ✅ **CensusQueryAgent** - Multi-step ReAct agent; tool list is defined in `src/agents/census_query_agent.py`
- ✅ **Agent Tools Suite** - Tools registered on the agent (10 as of current `census_query_agent.py`):
  - GeographyDiscoveryTool, GeographyValidationTool — discovery / validation
  - AreaResolutionTool — name-to-FIPS resolution
  - TableSearchTool — ChromaDB semantic search for Census tables
  - PatternBuilderTool — Census API URL pattern construction
  - StrictCensusApiTool — typed Census API execution
  - GeographyHierarchyTool, VariableValidationTool — hierarchy and variable checks
  - ChartTool — Plotly charts (bar, line, …)
  - TableTool — Data export (CSV, Excel, HTML)
- ✅ **Output Generation** - Automatic chart/table creation via output_node
- ✅ **Memory System** - SQLite checkpoints, user profiles, conversation history
- ✅ **Dual Interface** - CLI (main.py) and Web (streamlit_app.py) both functional
- ✅ **PDF Export** - Session reports with embedded charts and tables (Streamlit only)
- ✅ **Test Coverage** - 9/9 main app tests passing, 6/6 e2e workflow tests passing

### Architecture Evidence
- **Graph compiles**: `app.py` creates valid LangGraph workflow
- **Agent integration**: `src/workflows/agent.py` calls `CensusQueryAgent.solve()`
- **Tool registration**: Tools are registered in `src/agents/census_query_agent.py`
- **Output processing**: `src/workflows/output.py` generates charts/tables from agent results

> **Technical Details**: See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) for complete specifications. Note: ARCHITECTURE.md describes the design; this README reflects actual working implementation.

## 🏗️ Architecture

The application uses an **agent-first architecture**: deterministic gating nodes normalize time/benchmark/comparison intent, then the agent runs multi-step tool loops, then output and memory persist results.

```
User Question → Gating (temporal / benchmark / comparison) → Agent + tools → Metrics / output → Memory
```

### LangGraph Workflow
**Current flow** (see `app.py` for conditional edges):

```
memory_load → temporal → benchmark → comparison → agent → comparison_metrics → output → memory_write
```

The agent still owns repeated tool execution and answer synthesis; upstream nodes set or clarify `plan` before and between agent turns where applicable.

### Data Ownership Rule

The intended separation is:

- **Core workflow state** keeps canonical typed data contracts
- **Output/export paths** derive presentation formats such as charts, tables, CSV, Parquet, and PDF artifacts from those typed objects

In other words, workflow state should store the source of truth, while file formats and render-ready table views are derived on demand downstream.

### Key Components

#### Agent Architecture (`src/agents/`)
- **`census_query_agent.py`** - Main reasoning agent that handles intent parsing, geography resolution, and data retrieval
- **Agent Tools Suite** - Specialized tools for Census API interaction, geography discovery, and table search

#### Processing Nodes (`src/workflows/`)
**Nodes wired in `app.py`:**
- **`memory.py`** — `memory_load_node`, `memory_write_node`
- **`temporal.py`** — `temporal_node`
- **`benchmark.py`** — `benchmark_node`
- **`comparison.py`** — `comparison_node`
- **`agent.py`** — `agent_reasoning_node` (CensusQueryAgent)
- **`comparison_metrics.py`** — `comparison_metrics_node`
- **`output.py`** — `output_node` (charts/tables from agent results)

#### Agent Tools (`src/tools/`)
Tools **registered on the agent** live in `src/agents/census_query_agent.py` (see `self.tools`). Implementations include:

- **`geography_discovery_tool.py`**, **`geography_validation_tool.py`**, **`geography_hierarchy_tool.py`**
- **`area_resolution_tool.py`**, **`pattern_builder_tool.py`**
- **`table_search_tool.py`**, **`variable_validation_tool.py`**
- **`strict_census_api_tool.py`** ( **`census_api_tool.py`** exists but is not currently in the agent list )
- **`chart_tool.py`**, **`table_tool.py`**

Additional modules such as **`table_validation_tool.py`** and **`geography_schemas.py`** support validation and schemas; whether the agent invokes them depends on the registered tool list above.

#### State Management (`src/state/`)
- **`types.py`** - Pydantic state models and typed workflow envelopes for `plan`, `artifacts`, and `final`

> **Detailed Architecture**: See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) for complete component specifications, agent tool descriptions, and implementation details.

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Quick Start

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd census_tool
   uv sync
   ```

2. **Build the Census variable index:**
   ```bash
   uv run python index/build_index.py
   ```
   This creates a ChromaDB collection with ACS 5-year variables (2012-2023).

3. **Choose your interface:**
   
   **Option A: Easy Launcher (Recommended)**
   ```bash
   uv run python launcher.py
   ```
   This will let you choose between CLI and Web interfaces.
   
   **Option B: Direct CLI Interface**
   ```bash
   uv run python main.py
   ```
   
   **Option C: Direct Web Interface**
   ```bash
   uv run streamlit run streamlit_app.py
   ```

## 🎮 How to Use the Application

### 🚀 Quick Start with Launcher (Recommended)

The easiest way to get started is with the launcher:

```bash
uv run python launcher.py
```

This will show you a menu to choose between:
- **📱 Web Interface**: Interactive charts, file downloads, visual conversation history
- **💻 CLI Interface**: Fast, script-friendly, full terminal control

### Command Line Interface

1. **Start the application:**
   ```bash
   uv run python main.py
   ```

2. **Follow the prompts:**
   - Enter your user ID (or press Enter for 'demo')
   - Enter your thread ID (or press Enter for 'main')

3. **Ask questions about Census data:**
   ```
   ❓ Your question: What's the population of New York City in 2023?
   ```

4. **Example conversation flow:**
   ```
   🏛️  Welcome to the Census Data Assistant!
   ==================================================
   Enter your user ID (or press Enter for 'demo'): 
   Enter your thread ID (or press Enter for a new thread): 
   
   👤 User: demo
   🧵 Thread: main
   
   Ask me about Census data! (Type 'quit' to exit)
   Examples:
     - What's the population of New York City?
     - Show me median income trends from 2015 to 2020
     - Compare population by county in California
   --------------------------------------------------
   
   ❓ Your question: What's the population of NYC in 2023?
   
   🔍 Processing your question...
   
   📊 Answer: The population of New York City in 2023 was 8,258,035 people according to ACS 5-year estimates.
   
   📁 Data saved to: data/B01003_001E_place_2023.csv
   📝 Footnote: Data from Census Bureau API, Variable B01003_001E (Total population)
   
   ❓ Your question: 
   ```

### Web Interface (Streamlit)

1. **Start the web interface:**
   ```bash
   uv run streamlit run streamlit_app.py
   ```

2. **Open your browser** and navigate to `http://localhost:8501`

3. **Features of the web interface:**
   - 📊 **Interactive Charts**: Time series data displayed as interactive Plotly charts
   - 📥 **File Downloads**: Download CSV files directly from the browser
   - 📜 **Conversation History**: Visual history of your questions and answers
   - ⚙️ **Settings Panel**: Configure user ID and thread ID in the sidebar
   - 📱 **Responsive Design**: Works on desktop, tablet, and mobile devices
   - 🔍 **Example Questions**: Click example buttons to get started quickly

### Interactive Features

#### Conversation Memory
- **Follow-up questions**: Ask "What about last year?" and the app remembers your previous query
- **User preferences**: Your default geography and preferred datasets are remembered
- **Thread continuity**: Continue conversations across sessions using the same thread ID

#### Geographic Flexibility
```
❓ Your question: Population of California
❓ Your question: What about Los Angeles County?
❓ Your question: Show me NYC population trends from 2015 to 2020
```

#### Data Types Supported
- **Single values**: "Population of NYC in 2023"
- **Time series**: "Income trends from 2015 to 2020"
- **Geographic comparisons**: "Population by county in Texas"

### Advanced Usage

#### Custom User IDs
```bash
# Use different user IDs to maintain separate profiles
❓ Your question: [as user 'john']
❓ Your question: [as user 'research_team']
```

#### Thread Management
```bash
# Continue specific conversations
Enter your thread ID: project_analysis_2024
Enter your thread ID: quick_queries
```

#### Data Export
- All results are automatically saved as CSV files in the `data/` directory
- File names follow the pattern: `{variable}_{level}_{year}.csv`
- Preview data is shown in the terminal/web interface

### Troubleshooting Usage

#### If the app says "No variables found":
```bash
# Rebuild the index
uv run python index/build_index.py
```

#### If you get API errors:
```bash
# Check your internet connection
# The app will automatically retry with exponential backoff
```

#### If responses seem slow:
```bash
# Check the cache directory - subsequent queries should be faster
ls data/  # View cached data files
```

### Example Session Walkthrough

```bash
$ uv run python main.py

🏛️  Welcome to the Census Data Assistant!
==================================================
Enter your user ID (or press Enter for 'demo'): 
Enter your thread ID (or press Enter for a new thread): 

👤 User: demo
🧵 Thread: main

Ask me about Census data! (Type 'quit' to exit)
Examples:
  - What's the population of New York City?
  - Show me median income trends from 2015 to 2020
  - Compare population by county in California
--------------------------------------------------

❓ Your question: What's the population of New York City?

🔍 Processing your question...

📊 Answer: The population of New York City is 8,258,035 people according to ACS 5-year estimates for 2023.

📁 Data saved to: data/B01003_001E_place_2023.csv
📝 Footnote: Data from Census Bureau API, Variable B01003_001E (Total population)

❓ Your question: What about the median income?

🔍 Processing your question...

📊 Answer: The median household income in New York City is $70,663 according to ACS 5-year estimates for 2023.

📁 Data saved to: data/B19013_001E_place_2023.csv
📝 Footnote: Data from Census Bureau API, Variable B19013_001E (Median household income in the past 12 months)

❓ Your question: Show me income trends from 2015 to 2020

🔍 Processing your question...

📊 Answer: Here are the median household income trends for New York City from 2015 to 2020:

Year | Median Income
-----|-------------
2015 | $60,828
2016 | $62,935
2017 | $64,894
2018 | $67,214
2019 | $69,407
2020 | $70,663

📁 Data saved to: data/income_trends_2015_2020.csv
📝 Footnote: Data from Census Bureau API, Variables B19013_001E (Median household income)

❓ Your question: quit

👋 Goodbye!
```

## 💡 Quick Start Examples

### First Time Setup & Usage
```bash
# 1. Install dependencies
uv sync

# 2. Build the Census variable index (one-time setup)
uv run python index/build_index.py

# 3. Start the application
uv run python main.py

# 4. Use the app interactively
Enter your user ID: demo
Enter your thread ID: main
❓ Your question: What's the population of New York City?
```

### Sample Questions You Can Ask
```bash
# Population queries
"What's the population of New York City?"
"Population of California in 2023"
"Population by county in Texas"

# Income queries  
"Median income in NYC"
"Hispanic median income trends from 2015 to 2020"
"Income comparison across states"

# Geographic variations
"Population of Los Angeles County"
"Median income by county in New York"
"Nationwide population trends"

# Time series
"Population changes in NYC from 2015 to 2020"
"Income trends over time in California"
```

### Advanced Features
- **Conversation Memory**: Ask follow-up questions like "What about last year?" 
- **Geographic Flexibility**: Supports place, state, county, and national queries
- **Intelligent Fallbacks**: Graceful handling of ambiguous or unclear requests
- **Data Export**: Results saved as CSV files with preview displays

## 🧪 Testing

The project includes comprehensive test coverage with **all tests passing**:

```bash
# Run all tests
uv run pytest app_test_scripts/ -v

# Run specific test modules
uv run pytest app_test_scripts/test_main_app.py -v        # 9/9 passing
uv run pytest app_test_scripts/test_e2e_workflows.py -v   # 6/6 passing
uv run pytest app_test_scripts/test_memory.py -v
uv run pytest app_test_scripts/test_displays.py -v
```

### Test Coverage (Verified Working)
- ✅ **Main App Integration** - Graph compilation, state creation, user input processing (9/9 tests)
- ✅ **End-to-End Workflows** - Population queries, income trends, county comparisons, error handling (6/6 tests)
- ✅ **Memory Management** - Profile updates, cache management, retention policies
- ✅ **Display Functions** - Result formatting and visualization
- ✅ **PDF Generation** - Session export with charts and tables
- ✅ **Dynamic Geography** - Geography enumeration and resolution
- ✅ **Cache Performance** - Data caching and retrieval optimization

### Test Evidence
```bash
# Verify current status
uv run pytest app_test_scripts/test_main_app.py -v
# Output: 9 passed in 3.48s

uv run pytest app_test_scripts/test_e2e_workflows.py -v
# Output: 6 passed in 0.03s
```

## ⚙️ Configuration

### Application Settings

Key settings in `config.py`:

```python
# Retention Policies
RETENTION_DAYS = 90
CACHE_MAX_FILES = 2000
CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2GB

# API Settings
CENSUS_API_TIMEOUT = 30
CENSUS_API_MAX_RETRIES = 6
CENSUS_API_VARIABLE_LIMIT = 48

# Performance
MAX_CONCURRENCY = 5
RETRIEVAL_TOP_K = 12
CONFIDENCE_THRESHOLD = 0.7
```

### LLM Provider Configuration

The application uses a centralized LLM factory (`src/llm/factory.py`) that supports multiple providers with automatic compatibility handling.

#### Supported Models

**OpenAI:**
- `gpt-4o`, `gpt-4o-mini` - Standard Chat Completions API
- `gpt-4.1` - Chat Completions API compatible
- `gpt-5`, `gpt-5-mini` - Responses API only (requires special handling)
- `o1`, `o1-preview`, `o1-mini` - Reasoning models, Responses API
- `o3`, `o3-mini` - Advanced reasoning models, Responses API

**Anthropic:**
- `claude-sonnet-4-5-20250929` - Latest Claude Sonnet 4.5
- `claude-3-5-sonnet-20241022` - Legacy Claude Sonnet
- `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, `claude-3-haiku-20240307` - Legacy models

**Google Gemini:**
- `gemini-2.5-pro`, `gemini-2.5-flash` - Latest Gemini 2.5 models
- `gemini-2.0-pro`, `gemini-2.0-flash` - Gemini 2.0 models
- `gemini-1.5-pro`, `gemini-1.5-flash` - Legacy Gemini 1.5 models

#### Configuring Your LLM

Edit `src/llm/config.py` to set your provider and model:

```python
LLM_CONFIG = {
    "provider": "openai",  # or "anthropic" or "google"
    "model": "gpt-4o",
    "temperature": 0.1,
    "temperature_text": 0.5,
    "max_tokens": 2000,
    "timeout": 30,
    "fallback_model": "gpt-4o-mini",
}
```

#### Known Compatibility Issues

**Gemini 2.5 Flash Timeout (504 Deadline Exceeded):**
- **Issue**: Gemini 2.5 Flash may produce large outputs that exceed the 30-second timeout when generating complex Census data responses
- **Symptoms**: "504 Deadline Exceeded" error when agent returns large JSON responses
- **Workaround**: Use `gpt-4o`, `gpt-4.1`, or `claude-sonnet-4-5-20250929` for queries requiring large output responses
- **Future**: Consider increasing `max_output_tokens` and `timeout` for Gemini-specific configuration

**GPT-5 Responses API Compatibility:**
- GPT-5 and O-series models (o1, o3) use OpenAI's Responses API, which has different parameter requirements
- The factory automatically handles this with `.bind(stop=None)` and `output_version="responses/v1"`
- No manual configuration needed - just set `model="gpt-5"` and the factory applies the correct settings

#### Environment Variables

**Required for LLM APIs:**
```bash
# OpenAI (required for OpenAI models)
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic (required for Claude models)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google (required for Gemini models)
GOOGLE_API_KEY=your_google_api_key_here
```

**Optional: LangSmith Performance Tracing**
```bash
# Enable LangSmith tracing for performance monitoring
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=census-tool

# These are optional for debugging and monitoring only
# They enable visualization of agent execution traces, LLM calls, and tool usage
```

Create a `.env` file in the project root with these variables:
```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Optional: LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=census-tool
```

## 📁 Project Structure

Layout of the repository (omitting editor-only folders, virtualenvs, pytest/ruff/mypy caches, and `__pycache__`):

```
census_tool/
├── .cursor/                      # Cursor rules, skills, plans
├── .github/workflows/            # CI (e.g. ci.yml)
├── .release_notes/               # Version notes (optional archive)
├── app_description/             # Deep-dive specs and references
│   ├── ARCHITECTURE.md
│   ├── CENSUS_DISCUSSION.md
│   ├── geography_summaries/
│   ├── langchain_migration/
│   └── output_format_docs/
├── app_test_scripts/            # pytest: test_*.py (integration, contracts, tools)
├── articles/                      # Long-form notes / drafts
├── chroma/                      # ChromaDB on-disk store (runtime / local)
├── data/                        # API downloads, charts, caches (runtime)
│   ├── charts/
│   ├── geography_cache/
│   ├── geography_levels_cache/
│   └── tables/
├── docs/                        # Phase-1 notes, typed-contracts primer, track-2 framework, review notebook
├── index/                       # Index builders and query helpers
│   ├── build_index.py           # Variable/table Chroma index (one-time setup)
│   ├── build_index_table.py
│   ├── build_geography_index.py
│   └── read_query.py
├── logs/                        # cli, streamlit, telemetry (runtime)
├── memory/                      # Profiles / session-related files (runtime)
├── migration_evidence/          # Baseline manifests and migration snapshots
├── src/
│   ├── agents/
│   │   └── census_query_agent.py
│   ├── api/
│   │   └── displays.py
│   ├── clients/
│   │   ├── census_api_utils.py, chroma_utils.py, file_utils.py
│   │   ├── pdf_generator.py, session_logger.py, telemetry.py
│   ├── domain/
│   │   ├── geography_registry.py, geo_utils.py, census_groups.py
│   │   ├── text_utils.py, time_utils.py, clarification_templates.py
│   │   ├── census_tool_contract.py, census_client_contract.py, agent_output_contract.py
│   │   ├── temporal_contract.py, benchmark_contract.py, comparison_plan.py
│   │   ├── planning_tool_contracts.py, comparison_metric_contract.py
│   │   ├── final_output_contract.py, rendered_output_contract.py, presentation_contract.py
│   │   └── variable_metada_contract.py
│   ├── llm/
│   │   ├── config.py, factory.py, factory_legacy.py
│   │   ├── category_detector.py, geography_resolver.py, intent_enhancer.py
│   ├── locations/               # Reference CSVs (states, counties)
│   │   ├── states_abbrev.csv, counties_processed.csv
│   ├── services/
│   │   ├── dataset_geography_validator.py, variable_validator.py
│   │   ├── enumeration_detector.py, memory_utils.py, temporal_policy.py
│   │   ├── benchmark_policy.py, comparison_plan_policy.py, comparison_metric_compute.py
│   │   ├── dataframe_utils.py, census_render_adapter.py
│   │   ├── conversation_summarizer.py, conversation_history.py
│   │   ├── presentation_routing.py, footnote_generator.py
│   ├── state/
│   │   └── types.py
│   ├── tools/                   # LangChain tools (registry in census_query_agent)
│   │   ├── geography_discovery_tool.py, geography_validation_tool.py
│   │   ├── geography_hierarchy_tool.py, geography_schemas.py
│   │   ├── area_resolution_tool.py, pattern_builder_tool.py
│   │   ├── table_search_tool.py, table_validation_tool.py, variable_validation_tool.py
│   │   ├── strict_census_api_tool.py, census_api_tool.py, json_parse.py
│   │   ├── chart_tool.py, table_tool.py
│   ├── workflows/               # LangGraph nodes (wired in app.py)
│   │   ├── memory.py, agent.py, output.py
│   │   ├── temporal.py, benchmark.py, comparison.py, comparison_metrics.py
│   └── __init__.py
├── test_questions/              # Example or regression question sets
├── AGENTS.md                    # Layer order, Cursor/bootstrap-SLIM layout leg
├── SPEC.md                      # Bootstrap-SLIM spec index
├── app.py                       # StateGraph definition, checkpointing
├── config.py
├── Dockerfile
├── .dockerignore
├── launcher.py
├── main.py
├── streamlit_app.py
├── pyproject.toml
├── uv.lock
├── README.md
├── ARCHITECTURE_GUIDE.md
└── USAGE_GUIDE.md
```

**Runtime artifacts** (often gitignored or machine-local): `checkpoints.db` (LangGraph SQLite saver), contents of `data/`, `memory/`, `chroma/`, `logs/`.

**Graph wiring**: see `app.py` — `memory_load` → `temporal` → `benchmark` → `comparison` → `agent` → `comparison_metrics` → `output` → `memory_write`, with conditional edges to `output` when clarification is required.

**Legend**: Folders under `data/`, `memory/`, `chroma/`, `logs/` are populated at runtime, not shipped as canonical source trees.

## PDF Export Feature

The Streamlit interface includes a PDF export feature that allows you to download your complete session as a formatted report.

### How to Use

1. Ask questions and generate charts/tables in the Streamlit app
2. Click "📥 Download Session as PDF" in the sidebar
3. The PDF will be generated and downloaded automatically

### What's Included

- **Cover page** with session metadata (user, date, query count)
- **All conversations** with questions and answers
- **Embedded charts** as high-quality images
- **Data tables** formatted for readability
- **Professional styling** with headers, page numbers, and proper formatting

### File Location

PDFs are downloaded to your browser's default download folder with timestamped filenames (e.g., `census_session_20241201_143022.pdf`).

### Error Handling

The system gracefully handles missing files and will skip unavailable charts/tables while still generating a complete PDF report.

## 🔧 Key Technologies

- **LangGraph** - Workflow orchestration and state management with agent integration
- **LangChain Agents** - Multi-step reasoning with ReAct pattern and tool usage
- **ChromaDB** - Vector database for semantic table and variable search
- **Census API** - Official US Census Bureau data access with complex pattern support
- **Plotly** - Interactive data visualization and chart generation
- **Pandas** - Data processing and manipulation
- **SQLite** - Conversation checkpointing and persistence
- **uv** - Fast Python package management

## 🎯 Supported Geography Levels

The agent-based architecture supports dynamic geography discovery and pattern building for complex Census API requirements:

### Basic Levels
- **Place** - Cities and towns (e.g., New York City)
- **State** - US states and territories
- **County** - Counties within states
- **Nation** - United States as a whole

### Complex Geography Patterns (Via Agent)
- **Metropolitan Statistical Areas (MSAs)** - Core-based statistical areas
- **Metropolitan Divisions** - Sub-areas within large MSAs  
- **Combined Statistical Areas (CSAs)** - Groups of adjacent CBSAs
- **New England City and Town Areas (NECTAs)** - New England equivalents
- **School Districts** - Unified, elementary, and secondary districts
- **Urban Areas** - Densely developed areas
- **ZIP Code Tabulation Areas (ZCTAs)** - Approximate ZIP code areas
- **Census Tracts and Block Groups** - Small area geography
- **Tribal Areas** - American Indian and Alaska Native areas

> **Dynamic Support**: The agent can dynamically discover and build patterns for 144+ geography types as documented in the Census API. See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) for detailed geography capabilities.

## 📊 Data Sources & Categories

### Supported Data Categories
- **Detail Tables (B/C series)** - High granularity demographic data via `acs/acs5`
- **Subject Tables (S series)** - Topic-specific summaries via `acs/acs5/subject`
- **Profile Tables (DP series)** - Comprehensive demographic profiles via `acs/acs1/profile`
- **Comparison Tables (CP series)** - Multi-year comparisons via `acs/acs5/cprofile`
- **Selected Population Profiles (S0201 series)** - Race/ethnicity profiles via `acs/acs1/spp`

### Coverage
- **ACS 5-Year Estimates** (2012-2023) - Primary dataset with comprehensive coverage
- **Variable Coverage** - Population, income, education, housing, demographics, and specialized topics
- **Dynamic Table Discovery** - Agent discovers relevant tables based on user queries

## 🔒 Privacy & Security

- **Local Processing** - All data processing happens locally
- **No External APIs** - Only calls to the public Census API
- **Data Retention** - Configurable retention policies with automatic cleanup
- **User Isolation** - Separate profiles and histories per user

## 🚧 Future Enhancements

### Planned Features
- **Additional Datasets** - ACS 1-Year and Decennial Census integration
- **Advanced Analytics** - Statistical analysis and trend detection beyond current capabilities
- **Geographic Mapping** - Interactive maps showing spatial data distributions
- **Export Formats** - Parquet and JSON output options (CSV/Excel already supported)
- **Performance Optimization** - Further caching and query optimization for very large datasets
- **LangChain Upgrade** - Migrate to the next LangChain release (post-`0.3.x`) and update agent execution away from the deprecated `AgentExecutor`
- **API Endpoint** - RESTful API for programmatic access to agent capabilities

### Already Implemented
- ✅ **PDF Report Generation** - Working in Streamlit interface (`src/clients/pdf_generator.py`)
- ✅ **Chart Generation** - Plotly charts via ChartTool
- ✅ **Table Export** - CSV, Excel, HTML via TableTool
- ✅ **Data Caching** - 90-day retention with automatic cleanup

> **Extensibility**: The agent-first architecture supports new features through additional tools registered in CensusQueryAgent.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `uv run pytest`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

**Import Errors**: Ensure you're using `uv run` for all commands to use the correct virtual environment.

**Index Build Fails**: Check internet connection and Census API availability.

**Memory Issues**: Adjust `CACHE_MAX_BYTES` in `config.py` for systems with limited storage.

**API Rate Limits**: The application includes automatic retry logic with exponential backoff.

### Reset Application
To start fresh:
```bash
rm -rf data/ memory/ chroma/ checkpoints.db
uv run python index/build_index.py
```

### Architecture Issues
For technical implementation questions, agent tool issues, or architecture problems, see **[ARCHITECTURE.md](app_description/ARCHITECTURE.md)** which contains detailed component specifications, current implementation status, and troubleshooting guidelines.

---

*Built with ❤️ for the Census data community*