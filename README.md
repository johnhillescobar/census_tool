# Census Tool

A local Census QA application that answers questions about US Census data.

## Features

- **Intent Analysis** - Understands census-related questions
- **Geography Resolution** - Resolves locations like "NYC" to Census codes
- **Variable Retrieval** - Finds relevant Census variables using semantic search
- **Data Fetching** - Retrieves data from Census API with caching
- **Response Generation** - Formats answers with proper footnotes

## Quick Start

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Build the Census variable index:
   ```bash
   python index/build_index.py
   ```

3. Run the application:
   ```bash
   python app.py
   ```

## Project Status

- ✅ Core architecture and state management
- ✅ Intent analysis and geography resolution
- ✅ Variable retrieval and planning
- ✅ Data fetching with caching
- ⚠️ Response generation (in progress)

## Testing

Run tests to verify functionality:
```bash
uv run python test_plan.py
uv run python test_data.py
```
