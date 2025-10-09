#!/usr/bin/env python3
"""
Simple test script to validate the Census Data Assistant system
without interactive prompts
"""

import sys
import os
from pathlib import Path
import logging
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from app import create_census_graph
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_census_query(user_id: str, thread_id: str, query: str):
    """Test a census query end-to-end"""

    print(f"Testing Query: '{query}'")
    print(f"User: {user_id}, Thread: {thread_id}")
    print("-" * 60)

    try:
        # Initialize the graph
        graph = create_census_graph()

        # Create initial state
        initial_state = CensusState(
            messages=[{"role": "user", "content": query}],
            user_id=user_id,
            thread_id=thread_id,
        )

        # Run the graph
        config = RunnableConfig(
            configurable={"thread_id": thread_id, "user_id": user_id}
        )

        result = graph.invoke(initial_state, config=config)

        # Display results
        print("SUCCESS - Query completed")
        print("\nRESULTS:")
        if result.get("final"):
            print(f"Answer: {result['final'].get('answer_text', 'No answer text')}")
        else:
            print("No final answer generated")

        print(f"\nLOGS:")
        for log in result.get("logs", []):
            print(f"  - {log}")

        if result.get("error"):
            print(f"\nERROR: {result['error']}")

        return result

    except Exception as e:
        print(f"FAILED - Error: {str(e)}")
        logger.exception("Test failed")
        return None


def main():
    """Run system tests"""

    print("Census Data Assistant - System Test")
    print("=" * 60)

    # Test cases
    test_cases = [
        ("test_user", "test_thread", "What is the population of NYC?"),
        ("test_user", "test_thread", "What is the population of New York City?"),
        ("test_user", "test_thread", "Show me population data for Chicago"),
    ]

    results = []

    for user_id, thread_id, query in test_cases:
        print(f"\nTEST {len(results) + 1}/3")
        result = test_census_query(user_id, thread_id, query)
        results.append(result)
        print("\n" + "=" * 60)

    # Summary
    print("\nTEST SUMMARY:")
    successful = sum(1 for r in results if r and not r.get("error"))
    print(f"Successful: {successful}/3")
    print(f"Failed: {3 - successful}/3")

    if successful == 0:
        print("\nCRITICAL: All tests failed - system needs immediate attention")
    elif successful < 3:
        print("\nPARTIAL: Some tests failed - system needs fixes")
    else:
        print("\nEXCELLENT: All tests passed - system is working!")


if __name__ == "__main__":
    main()
