# 🏛️ Census Data Assistant - Usage Guide

**Status:** Operational — **target** is agent-first grounded planning; **current code** still uses legacy pre-agent `geography_node` on some paths (see [`docs/agent-first-grounded-planning.md`](docs/agent-first-grounded-planning.md)).

> **📋 Technical Documentation**: [`ARCHITECTURE.md`](app_description/ARCHITECTURE.md) (system design) · [`CENSUS_DISCUSSION.md`](app_description/CENSUS_DISCUSSION.md) (Census API decision space) · [`agent-first-grounded-planning.md`](docs/agent-first-grounded-planning.md) (target vs legacy)

## What to expect

- The assistant **reasons** about your question in natural language — topic, geography, time, comparisons.
- It may **ask clarifying questions** when multiple grounded table or geography options exist (target: readable labels and a recommended default — not only `table_0` codes).
- When you do not specify a data category, it may answer with a **broad measure** (e.g. Detail table) and suggest finer follow-ups (race, age, Subject tables, etc.).
- Year defaults to **latest available** (e.g. 2024) when you do not state a year, after temporal normalization.
- Multi-step queries (enumerate areas → pick code → fetch → compare) are normal agent behavior.

## 🚀 Quick Start

### Option 1: Easy Launcher (Recommended)
```bash
uv run python launcher.py
```
Choose between CLI and Web interfaces from the menu.

### Option 2: Direct CLI Interface
```bash
uv run python main.py
```

### Option 3: Direct Web Interface
```bash
uv run streamlit run streamlit_app.py
```
Then open http://localhost:8501 in your browser.

## 📱 Web Interface Features

### Interactive Charts
- **Agent-Generated Charts** - Automatic chart creation via CensusQueryAgent's ChartTool
- **Interactive Plotly Charts** - Time series, bar charts, and line charts with dynamic data
- **Hover tooltips** with detailed information and data points
- **Zoom and pan capabilities** for data exploration
- **Download options** - Save charts as PNG, SVG, or HTML

### File Downloads
- **Agent-Generated Tables** - Automatic table creation via CensusQueryAgent's TableTool
- **Multiple Formats** - CSV, Excel, and HTML export options
- **Direct Downloads** - Download files directly from the browser
- **Auto-Save** - Files are automatically saved to the `data/` directory

### Conversation History
- Visual history of questions and answers in the sidebar
- Expandable conversation entries
- Clear conversation button to start fresh

### Settings Panel
- Configure User ID and Thread ID in the sidebar
- Settings persist across sessions
- Separate profiles for different users

## 💻 CLI Interface Features

### Fast and Efficient
- No browser overhead
- Instant responses
- Perfect for scripting and automation

### Full Terminal Control
- Complete keyboard navigation
- Copy/paste support
- Terminal-based data display

### Advanced Features
- **Agent Reasoning Logs** - Detailed system logs showing agent's multi-step reasoning process
- **Tool Execution Visibility** - See which agent tools are being used for each query
- **Raw data access** - Access to agent-generated census data and metadata
- **Command-line friendly output** - Terminal-optimized display of results

## 🔄 Both Interfaces Share

### Core Functionality
- Same LangGraph workflow with multi-step agent reasoning (target: agent owns retrieval and API execution end-to-end)
- Identical data processing using CensusQueryAgent and specialized tools
- Same caching system and conversation memory
- Agent-based query processing with dynamic geography discovery

### Data Sources & Categories
- **Detail Tables (B/C series)** - High granularity demographic data
- **Subject Tables (S series)** - Topic-specific summaries  
- **Profile Tables (DP series)** - Comprehensive demographic profiles
- **Comparison Tables (CP series)** - Multi-year comparisons
- **Selected Population Profiles (S0201 series)** - Race/ethnicity profiles
- **ACS 5-Year Estimates** (2012-2023) with comprehensive coverage

### Geography Support
- **Basic Levels**: Place, state, county, nation
- **Complex Geography**: MSAs, metropolitan divisions, school districts, urban areas, ZCTAs, census tracts, tribal areas, and 144+ other patterns via agent discovery

### Example Questions
- "What's the population of New York City?"
- "Show me median income trends from 2015 to 2020"
- "Compare population by county in California"
- "What's the population of the New York Metropolitan Area?"
- "Show me school districts in Texas"
- "Population data for Navajo Nation census tracts"

## 🎯 When to Use Which Interface

### Use Web Interface When:
- You want visual charts and graphs
- You need to download files easily
- You prefer a modern, interactive UI
- You're sharing results with others
- You want to see conversation history visually

### Use CLI Interface When:
- You need fast, scriptable access
- You're working in a terminal environment
- You want minimal resource usage
- You're automating data collection
- You prefer keyboard-only interaction

## 🔧 Technical Details

### Architecture (current code vs target)

**Target graph:** `memory_load → temporal → agent (plan + execute) → validate → comparison_metrics → output → memory_write` — see [`docs/agent-first-grounded-planning.md`](docs/agent-first-grounded-planning.md).

**Current graph (legacy):** `memory_load → temporal → geography → benchmark → comparison → agent → comparison_metrics → output → memory_write`

Both interfaces use the same LangGraph workflow in `app.py`. Key modules:

- **`src/workflows/agent.py`** — `agent_reasoning_node`; **legacy:** skipped when `requires_clarification=True`
- **`src/workflows/geography.py`** — **legacy:** pre-agent planner (`geography_node`); target: validator harness only
- **`src/agents/census_query_agent.py`** — agent tools: Chroma search, geography enumeration, **Census API composition and execution**
- **`src/tools/`** — `TableSearchTool`, `GeographyDiscoveryTool`, `StrictCensusApiTool`, etc.
- **SQLite checkpoints** — conversation and pending clarification state

### Agent-based data flow (target)

1. **User input** → `memory_load_node` loads profile/history
2. **Temporal** → resolve year (default latest when unstated)
3. **Agent planning** → semantic Chroma retrieval; select table/geo/category or ask grounded clarification
4. **Validate** → harness rejects invented FIPS/table codes
5. **Agent execute** → compose `get`/`for`/`in`/dataset path; call Census tools (possibly multiple times)
6. **Output** → charts/tables from typed agent output; natural-language answer with assumptions and follow-up suggestions
7. **Memory write** → persist turn

> **Legacy path:** steps 3–5 may be partially performed by `geography_node` before the agent runs. Migration in progress.

### Test Evidence
```bash
# Verify architecture works end-to-end
uv run pytest app_test_scripts/test_main_app.py -v
# Output: 9 passed in 3.48s

uv run pytest app_test_scripts/test_e2e_workflows.py -v
# Output: 6 passed in 0.03s
```

> **Detailed flow:** [`ARCHITECTURE.md`](app_description/ARCHITECTURE.md) · [`agent-first-grounded-planning.md`](docs/agent-first-grounded-planning.md)

### Caching
- 90-day retention policy
- Automatic cleanup
- Shared cache between interfaces
- Parallel processing for multi-year queries

## 🆘 Troubleshooting

### Web Interface Issues
- **Port conflicts**: Try `--server.port 8502`
- **Browser not opening**: Manually go to http://localhost:8501
- **Slow loading**: Check internet connection for Census API

### CLI Interface Issues
- **Import errors**: Use `uv run python main.py`
- **No data**: Rebuild index with `uv run python index/build_index.py`
- **API errors**: Check internet connection

### Both Interfaces
- **Memory issues**: Adjust `CACHE_MAX_BYTES` in `config.py`
- **API rate limits**: Automatic retry with exponential backoff
- **Reset everything**: Delete `data/`, `memory/`, `chroma/` directories
- **Agent issues**: For agent tool problems or complex query failures, see [ARCHITECTURE.md](app_description/ARCHITECTURE.md)

## 📊 Data Export

### CSV Files
- Automatically saved to `data/` directory
- Web interface: Download button
- CLI interface: File path displayed
- Generated by agent's TableTool and output_node

### Chart Images
- Automatic generation via agent's ChartTool and output_node
- Web interface: Right-click to save charts or download buttons
- Export formats: PNG, SVG, HTML
- Interactive: Zoom, pan, hover tooltips with Plotly integration

### Generated Outputs
- **Charts**: Bar charts, line charts automatically created based on data type
- **Tables**: CSV, Excel, HTML formats via agent's TableTool
- **Formatted Reports**: Natural language answers with data summaries

## 🔮 Future Enhancements

- **PDF Report Generation** - Comprehensive reports with embedded charts and tables
- **Geographic mapping** - Interactive maps showing geographic data
- **Advanced Analytics** - Statistical analysis and trend detection
- **Export to Parquet** - High-performance data formats
- **API endpoint** - Programmatic access to agent capabilities

> **Architecture direction:** Agent-first grounded planning supports these enhancements through additional tools and agent capabilities. See [`docs/agent-first-grounded-planning.md`](docs/agent-first-grounded-planning.md).
