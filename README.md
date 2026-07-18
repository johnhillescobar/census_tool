# Census Tool

A sophisticated local Census QA application that answers questions about US Census data using LangGraph, ChromaDB, and the Census API. This tool uses an **agent-first architecture** with multi-step reasoning to handle complex Census API queries, providing intelligent query processing, semantic variable retrieval, and comprehensive data caching with conversation memory.

## Reasoning-Node-First Principle

Canonical principle: deterministic contracts and workflow/service steps are reliability scaffolding that empower AI reasoning nodes/components and must not replace AI reasoning nodes/components.

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

**Current Status**: 🟡 **Track 2 operational** — deterministic planning + agent execution wired and covered by contract tests; live LLM/API integration tests require API keys.

### Verified Working Components
- ✅ **Track 2 LangGraph workflow** — 8 nodes with conditional routing (`memory_load → temporal → benchmark → comparison → agent → comparison_metrics → output → memory_write`)
- ✅ **Typed planning contracts** — `TemporalIntent`, `BenchmarkIntent`, `ComparisonPlan` in `src/domain/` with fail-to-clarification behavior
- ✅ **CensusQueryAgent** — ReAct agent with 11 registered tools (see [ARCHITECTURE.md](app_description/ARCHITECTURE.md))
- ✅ **Deterministic comparison metrics** — `comparison_metrics_node` + `comparison_metric_compute` service
- ✅ **Typed rendered outputs** — `RenderedArtifactSuccess` / `RenderedArtifactFailure` in `final.generated_files`
- ✅ **Presentation routing** — deterministic UI kind selection via `presentation_routing` service
- ✅ **Memory System** — SQLite checkpoints, user profiles, conversation history
- ✅ **Dual Interface** — CLI (`main.py`) and Web (`streamlit_app.py`)
- ✅ **PDF Export** — Session reports with embedded charts and tables (Streamlit only)
- 🟢 **Test Coverage** — 281 tests collected; **279 passed, 2 skipped** in full suite (~9 min); 244+ pass in fast unit subset without live LLM tests

### Architecture Evidence
- **Graph compiles**: `app.py` → `create_census_graph()` (see `graph.png`)
- **Planning nodes**: `src/workflows/temporal.py`, `benchmark.py`, `comparison.py`
- **Agent integration**: `src/workflows/agent.py` calls `CensusQueryAgent.solve()` with optional `AgentPlanContext`
- **Output processing**: `src/workflows/output.py` uses typed artifact contracts

> **Technical Details**: See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) — single source of truth for the current implementation.

## 🏗️ Architecture

The application uses a **reasoning-node-first architecture**: deterministic planning nodes prepare typed contracts, the agent executes Census retrieval, and downstream nodes render outputs.

```
User Question → Temporal/Benchmark/Comparison planning → Agent (tool loops) → Comparison metrics → Output → Result
```

### LangGraph Workflow
**Current flow** (8 nodes, conditional routing for clarification and benchmark bypass):

```
memory_load → temporal → benchmark → comparison → agent → comparison_metrics → output → memory_write
```

Planning nodes fail closed to clarification when input is ambiguous. When no comparison is requested, benchmark routing skips directly to the agent. See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) for the routing diagram.

### Key Components

#### Agent Architecture (`src/agents/`)
- **`census_query_agent.py`** - Main reasoning agent that handles intent parsing, geography resolution, and data retrieval
- **Agent Tools Suite** - Specialized tools for Census API interaction, geography discovery, and table search

#### Processing Nodes (`src/workflows/`)
**Active nodes** (wired in `app.py`):
- **`memory.py`** — `memory_load_node`, `memory_write_node`
- **`temporal.py`** — resolve temporal intent; clarification gate
- **`benchmark.py`** — resolve benchmark intent or mark not applicable
- **`comparison.py`** — build `ComparisonPlan` from temporal + benchmark
- **`agent.py`** — `agent_reasoning_node` (calls `CensusQueryAgent` with plan context)
- **`comparison_metrics.py`** — deterministic derived metrics from comparison rows
- **`output.py`** — chart/table rendering with typed `generated_files` artifacts
- **`graph_patch.py`** — `CensusGraphPatch` for typed LangGraph state updates

#### Agent Tools (`src/tools/`)
11 tools registered in `CensusQueryAgent` (see `src/agents/census_query_agent.py`):
- **`geography_discovery_tool.py`** — GeographyDiscoveryTool
- **`geography_validation_tool.py`** — GeographyValidationTool
- **`geography_hierarchy_tool.py`** — GeographyHierarchyTool
- **`area_resolution_tool.py`** — AreaResolutionTool
- **`table_search_tool.py`** — TableSearchTool (ChromaDB)
- **`variable_validation_tool.py`** — VariableValidationTool
- **`pattern_builder_tool.py`** — PatternBuilderTool
- **`census_api_tool.py`** — CensusAPITool
- **`strict_census_api_tool.py`** — StrictCensusApiTool (typed responses)
- **`chart_tool.py`** — ChartTool (also used by `output_node`)
- **`table_tool.py`** — TableTool (CSV, Excel, HTML)

`TableValidationTool` exists in `src/tools/` but is **not** registered on the agent.

#### State Management (`src/state/`)
- **`types.py`** — Pydantic `CensusState` with LangGraph reducers; typed `FinalResponseState` / `WorkflowArtifactsState` views
- **`workflow_plan.py`** — `WorkflowPlan` aggregate (`temporal`, `benchmark`, `comparison`, `requires_clarification`)

#### Domain & Services (`src/domain/`, `src/services/`)
- **Typed contracts** — `TemporalIntent`, `BenchmarkIntent`, `ComparisonPlan`, agent output, rendered artifacts
- **Policy services** — `temporal_policy`, `benchmark_policy`, `comparison_plan_policy`, `comparison_metric_compute`
- **Presentation** — `presentation_routing` for deterministic UI kind selection

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

The project includes broad contract and integration coverage:

```bash
# Run all tests (281 collected)
uv run pytest app_test_scripts/ -v

# Fast unit/contract subset (excludes live LLM integration tests)
uv run pytest app_test_scripts/ -q \
  --ignore=app_test_scripts/test_integration_agent_api.py \
  --ignore=app_test_scripts/test_census_query_agent.py \
  --ignore=app_test_scripts/test_e2e_workflows.py
```

### Test Coverage Areas
- **Graph & routing** — Track 2 workflow invoke, benchmark routing, graph patch contracts
- **Typed contracts** — temporal, benchmark, comparison, agent output, rendered output
- **Agent node wiring** — plan context, comparison rows, reasoning node behavior
- **Main app integration** — graph compilation, state creation (`test_main_app.py`)
- **Memory & caching** — profiles, retention, cache performance
- **PDF generation** — Streamlit session export
- **Live integration** — `test_census_query_agent.py`, `test_e2e_workflows.py` (require API keys)

### Test Evidence
```bash
uv run pytest app_test_scripts/ --collect-only -q
# Output: 281 tests collected

uv run pytest app_test_scripts/ -q
# Output: 279 passed, 2 skipped (~9 min full run)

uv run pytest app_test_scripts/ -q --ignore=app_test_scripts/test_integration_agent_api.py \
  --ignore=app_test_scripts/test_census_query_agent.py \
  --ignore=app_test_scripts/test_e2e_workflows.py
# Output: 244 passed, 2 skipped (~23s unit/contract subset)
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

```
census_tool/
├── src/
│   ├── domain/          # Typed contracts (TemporalIntent, ComparisonPlan, …)
│   │   ├── temporal_contract.py, benchmark_contract.py, comparison_plan.py
│   │   ├── agent_output_contract.py, rendered_output_contract.py
│   │   ├── geography_registry.py, geo_utils.py, text_utils.py
│   ├── services/        # Deterministic policy + compute
│   │   ├── temporal_policy.py, benchmark_policy.py, comparison_plan_policy.py
│   │   ├── comparison_metric_compute.py, presentation_routing.py
│   │   ├── memory_utils.py, variable_validator.py, footnote_generator.py
│   ├── clients/         # External I/O adapters
│   │   ├── census_api_utils.py, chroma_utils.py, file_utils.py
│   │   ├── session_logger.py, telemetry.py, pdf_generator.py
│   ├── agents/          # CensusQueryAgent (11 tools)
│   │   └── census_query_agent.py
│   ├── workflows/       # LangGraph nodes (8 active)
│   │   ├── memory.py, temporal.py, benchmark.py, comparison.py
│   │   ├── agent.py, comparison_metrics.py, output.py, graph_patch.py
│   ├── api/             # Presentation adapters
│   │   └── displays.py
│   ├── state/           # CensusState + WorkflowPlan
│   │   ├── types.py, workflow_plan.py
│   ├── tools/           # Agent tools (11 registered; TableValidationTool unused)
│   ├── llm/             # Factory, config, prompts
│   └── locations/       # Geography reference data
├── app_test_scripts/    # 281 tests (contract, routing, integration)
├── docs/                # track-2_framework.md, typed_contracts.md
├── app_description/     # ARCHITECTURE.md, output format specs
├── migration_evidence/  # Track baselines and gap registers
├── index/               # ChromaDB index builder
├── data/, memory/, chroma/   # Runtime (auto-created)
├── app.py               # LangGraph workflow (8 nodes)
├── main.py, streamlit_app.py, launcher.py
└── pyproject.toml
```

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
- ✅ **Track 2 deterministic planning** — temporal/benchmark/comparison nodes + typed contracts
- ✅ **Comparison metrics** — deterministic derived metrics node
- ✅ **Typed rendered outputs** — success/failure artifacts for charts and tables
- ✅ **Presentation routing** — deterministic UI kind from state
- ✅ **PDF Report Generation** — Streamlit session export (`src/clients/pdf_generator.py`)
- ✅ **Chart Generation** — Plotly charts via ChartTool and output_node
- ✅ **Table Export** — CSV, Excel, HTML via TableTool
- ✅ **Data Caching** — 90-day retention with automatic cleanup

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