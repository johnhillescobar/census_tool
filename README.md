# Census Tool

A sophisticated local Census QA application that answers questions about US Census data using LangGraph, ChromaDB, and the Census API. This tool provides intelligent query processing, semantic variable retrieval, and comprehensive data caching with conversation memory.

## 🚀 Features

### Core Functionality
- **Intent Analysis** - Heuristic parsing of census-related questions without requiring LLMs
- **Geography Resolution** - Resolves locations like "NYC" to Census API codes with support for multiple levels
- **Variable Retrieval** - Semantic search through Census variables using ChromaDB embeddings
- **Data Fetching** - Robust API calls with retry logic, caching, and parallel processing
- **Response Generation** - Formatted answers with proper footnotes and data previews
- **Memory Management** - User profiles, conversation history, and intelligent caching with retention policies

### Advanced Capabilities
- **Conversation Memory** - Maintains thread state and user preferences across sessions
- **Intelligent Caching** - 90-day retention with LRU eviction and size limits
- **Parallel Processing** - Concurrent API calls for multi-year data requests
- **Error Handling** - Graceful degradation with fallback responses and clarification prompts
- **Message Summarization** - Automatic conversation trimming to maintain performance

## 📋 Project Status

- ✅ **Core Architecture** - Complete LangGraph workflow with state management
- ✅ **Intent Analysis** - Heuristic parsing with robust rule-based logic
- ✅ **Geography Resolution** - Support for place, state, county, and nation levels
- ✅ **Variable Retrieval** - ChromaDB-based semantic search with confidence scoring
- ✅ **Data Fetching** - API integration with caching, retries, and parallel processing
- ✅ **Response Generation** - Single values, series, and table formatting
- ✅ **Memory System** - User profiles, history tracking, and cache management
- ✅ **Testing Suite** - Comprehensive test coverage for all major components
- ✅ **Configuration** - Centralized settings with environment management

## 🏗️ Architecture

### LangGraph Workflow
The application uses a sophisticated workflow with conditional routing:

```
memory_load → [summarizer] → intent → router → {
  ├─ not_census → end
  ├─ clarify → end
  └─ geo → retrieve → plan → data → answer → memory_write → end
}
```

### Key Components

#### State Management (`src/state/`)
- **`types.py`** - TypedDict definitions for CensusState and QuerySpec
- **`routing.py`** - Conditional routing logic for workflow control

#### Processing Nodes (`src/nodes/`)
- **`memory.py`** - Load/save user profiles and conversation history
- **`intent.py`** - Heuristic intent parsing with clarification detection
- **`geo.py`** - Geography resolution with level validation
- **`retrieve.py`** - ChromaDB-based variable retrieval with confidence scoring
- **`data.py`** - Census API integration with caching and parallel processing
- **`answer.py`** - Response formatting with footnotes and data previews

#### Utility Libraries (`src/utils/`)
- **`text_utils.py`** - Text processing, intent extraction, and answer formatting
- **`geo_utils.py`** - Geography code mappings and validation
- **`census_api_utils.py`** - API client with retry logic and error handling
- **`chroma_utils.py`** - ChromaDB client management and collection operations
- **`cache_utils.py`** - Cache signature computation and file management
- **`memory_utils.py`** - User profile updates and retention policy enforcement
- **`displays.py`** - Result formatting and user interface components

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

3. **Run the application:**
   ```bash
   uv run python main.py
   ```

### Alternative: Web Interface
```bash
uv run python app.py
```

## 🎮 How to Use the Application

### Command Line Interface (Recommended)

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

### Web Interface (Alternative)

1. **Start the web server:**
   ```bash
   uv run python app.py
   ```

2. **Open your browser** and navigate to the URL shown in the terminal (typically `http://localhost:8000`)

3. **Use the web interface** to ask questions about Census data

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

The project includes comprehensive test coverage:

```bash
# Run all tests
uv run pytest test_*.py -v

# Run specific test modules
uv run pytest test_intent.py -v
uv run pytest test_data.py -v
uv run pytest test_memory.py -v
```

### Test Coverage
- **Intent Analysis** - Question parsing and clarification detection
- **Geography Resolution** - Location mapping and validation
- **Variable Retrieval** - ChromaDB search and confidence scoring
- **Data Fetching** - API calls, caching, and error handling
- **Memory Management** - Profile updates and retention policies
- **Answer Generation** - Response formatting and footnote generation

## ⚙️ Configuration

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

## 📁 Project Structure

```
census_tool/
├── src/
│   ├── nodes/           # LangGraph processing nodes
│   ├── state/           # State management and routing
│   └── utils/           # Utility libraries
├── index/               # ChromaDB index builder
├── data/                # Cached Census data (runtime)
├── memory/              # User profiles and history (runtime)
├── chroma/              # ChromaDB persistent storage
├── test_*.py           # Test suites
├── main.py             # CLI application entry point
├── app.py              # Web interface entry point
└── config.py           # Configuration constants
```

## 🔧 Key Technologies

- **LangGraph** - Workflow orchestration and state management
- **ChromaDB** - Vector database for semantic variable search
- **Census API** - Official US Census Bureau data access
- **Pandas** - Data processing and manipulation
- **SQLite** - Conversation checkpointing and persistence
- **uv** - Fast Python package management

## 🎯 Supported Geography Levels

- **Place** - Cities and towns (e.g., New York City)
- **State** - US states and territories
- **County** - Counties within states
- **Nation** - United States as a whole

*Note: Tract and block group support planned for future releases*

## 📊 Data Sources

- **ACS 5-Year Estimates** (2012-2023) - Primary dataset for demographic and economic data
- **Variable Coverage** - Population, income, education, housing, and demographic characteristics
- **Future Expansion** - ACS 1-Year and Decennial Census support planned

## 🔒 Privacy & Security

- **Local Processing** - All data processing happens locally
- **No External APIs** - Only calls to the public Census API
- **Data Retention** - Configurable retention policies with automatic cleanup
- **User Isolation** - Separate profiles and histories per user

## 🚧 Future Enhancements

- **Tract/Block Group Support** - Geographic level expansion
- **Additional Datasets** - ACS 1-Year and Decennial Census integration
- **LLM Integration** - Optional AI-powered intent analysis
- **Advanced Analytics** - Statistical analysis and trend detection
- **Export Formats** - Parquet, Excel, and JSON output options

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

---

*Built with ❤️ for the Census data community*