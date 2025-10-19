# 🏛️ Census Data Assistant - Usage Guide

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
- Time series data displayed as interactive Plotly charts
- Hover tooltips with detailed information
- Zoom and pan capabilities
- Download charts as images

### File Downloads
- Download CSV files directly from the browser
- Files are automatically saved to the `data/` directory
- Download buttons appear for all data exports

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
- Detailed system logs
- Raw data access
- Command-line friendly output

## 🔄 Both Interfaces Share

### Core Functionality
- Same LangGraph workflow
- Identical data processing
- Same caching system
- Same conversation memory

### Data Sources
- ACS 5-Year Estimates (2012-2023)
- Population, income, demographics
- Geographic levels: place, state, county, nation

### Example Questions
- "What's the population of New York City?"
- "Show me median income trends from 2015 to 2020"
- "Compare population by county in California"
- "What's the median income in Los Angeles County?"

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
Both interfaces use the same underlying components:
- `app.py` - LangGraph workflow
- `src/` - Processing nodes and utilities
- `config.py` - Configuration settings
- SQLite checkpoints for conversation persistence

### Data Flow
1. User input → Intent analysis
2. Geography resolution
3. Variable retrieval (ChromaDB)
4. Data fetching (Census API)
5. Response formatting
6. Display (CLI or Web)

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

## 📊 Data Export

### CSV Files
- Automatically saved to `data/` directory
- Web interface: Download button
- CLI interface: File path displayed
- Format: `{variable}_{level}_{year}.csv`

### Chart Images
- Web interface: Right-click to save charts
- Export formats: PNG, SVG, HTML
- Interactive: Zoom, pan, hover tooltips

## 🔮 Future Enhancements

- Additional chart types (bar charts, heat maps)
- Geographic mapping integration
- Advanced statistical analysis
- Export to Excel/Parquet formats
- API endpoint for programmatic access

