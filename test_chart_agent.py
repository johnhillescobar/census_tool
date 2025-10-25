#!/usr/bin/env python3
"""
Test ChartTool integration with CensusQueryAgent
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Setup paths
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

load_dotenv()

from src.utils.agents.census_query_agent import CensusQueryAgent


def test_chart_request():
    """Test agent's ability to create charts"""
    print("Testing ChartTool with CensusQueryAgent...")

    # Create agent
    agent = CensusQueryAgent()

    # Test query that should trigger chart creation
    test_query = "Show me population by county in New York as a bar chart"
    intent = {"topic": "population", "geography": "county", "state": "New York"}

    print(f"\nQuery: {test_query}")
    print(f"Intent: {intent}")
    print("\nRunning agent...")

    try:
        result = agent.solve(user_query=test_query, intent=intent)

        print("\n=== AGENT RESULT ===")
        print(f"Result keys: {list(result.keys())}")

        # Check for census data
        if result.get("census_data"):
            print(f"Census data present: {type(result['census_data'])}")
            if (
                isinstance(result["census_data"], dict)
                and "data" in result["census_data"]
            ):
                data_rows = result["census_data"]["data"]
                if isinstance(data_rows, list) and len(data_rows) > 0:
                    headers = data_rows[0] if data_rows else []
                    print(f"Data headers: {headers}")
                    print(
                        f"Number of data rows: {len(data_rows) - 1 if len(data_rows) > 1 else 0}"
                    )

        # Check for answer text
        if result.get("answer_text"):
            print(f"\nAnswer: {result['answer_text']}")

        # Check for reasoning trace
        if result.get("reasoning_trace"):
            print(f"\nReasoning: {result['reasoning_trace']}")

        # Check if charts are mentioned
        if result.get("charts_needed"):
            print(f"\nCharts needed: {result['charts_needed']}")

        return result

    except Exception as e:
        print(f"Error running agent: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_agent_verbosely():
    """Run agent with verbose output to see tool calls"""
    print("\n" + "=" * 50)
    print("Running agent with verbose output...")
    print("=" * 50)

    agent = CensusQueryAgent()
    test_query = "Show me population by county in New York as a bar chart"
    intent = {"topic": "population", "geography": "county", "state": "New York"}

    try:
        result = agent.solve(user_query=test_query, intent=intent)
        return result
    except Exception as e:
        print(f"Error in verbose test: {e}")
        return None


if __name__ == "__main__":
    # Set logging level to see agent verbose output
    logging.basicConfig(level=logging.INFO)

    print("ChartTool Integration Test")
    print("=" * 30)

    # Test 1: Basic functionality
    result1 = test_chart_request()

    # Test 2: Check if charts directory has files after agent run
    print("\n" + "=" * 50)
    print("Checking charts directory...")

    charts_dir = "data/charts"
    if os.path.exists(charts_dir):
        chart_files = [
            f for f in os.listdir(charts_dir) if f.endswith((".png", ".html"))
        ]
        print(f"Chart files in {charts_dir}: {chart_files}")
        if chart_files:
            print("SUCCESS: Charts were generated!")
        else:
            print("FAILED: No chart files found")
    else:
        print(f"❌ Charts directory {charts_dir} does not exist")

    print("\nTest completed.")
