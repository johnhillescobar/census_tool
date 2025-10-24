# 🏛️ Census Data Assistant - Usage Guide

> **📋 Technical Documentation**: For detailed architecture information, see **[ARCHITECTURE.md](app_description/ARCHITECTURE.md)** - the single source of truth for the agent-first implementation.

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
- Same agent-first LangGraph workflow with multi-step reasoning
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

### Architecture
Both interfaces use the same agent-first architecture:
- `app.py` - LangGraph workflow with agent-based reasoning
- `src/nodes/agent.py` - CensusQueryAgent with multi-step reasoning
- `src/nodes/output.py` - Chart and table generation
- `src/tools/` - Specialized agent tools for Census API interaction
- `config.py` - Configuration settings
- SQLite checkpoints for conversation persistence

### Agent-Based Data Flow
1. User input → Agent reasoning (multi-step)
2. Agent uses tools: Geography discovery → Table search → API execution
3. Agent validates results and determines output format
4. Output generation: Charts, tables, formatted responses
5. Display (CLI or Web)

> **Detailed Flow**: See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) for complete agent architecture and tool specifications.

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

> **Current Architecture**: The agent-first architecture supports these enhancements through additional tools and agent capabilities. See [ARCHITECTURE.md](app_description/ARCHITECTURE.md) for implementation details.

