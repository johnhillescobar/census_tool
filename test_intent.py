"""
Test script for intent_node
"""

import logging
from src.nodes.intent import intent_node

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_intent_node():
    """Test the intent_node with various inputs"""

    # Test cases from the census_app.md specification
    test_cases = [
        "Population of NYC in 2023",
        "Hispanic income from 2012 to 2023 in NYC",
        "By county in NYC, population 2020",
        "What's 2+2?",  # Should be not_census
        "Population",  # Should need clarification
    ]

    for i, test_input in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: '{test_input}' ---")

        # Mock state with the test message
        state = {
            "messages": [{"role": "user", "content": test_input}],
            "profile": {},
            "history": [],
            "cache_index": {},
            "logs": [],
        }

        # Mock config
        config = {"user_id": "test_user", "thread_id": "test_thread"}

        # Test the intent node
        result = intent_node(state, config)

        # Display results
        intent = result.get("intent", {})
        print(f"✅ Is Census: {intent.get('is_census')}")
        print(f"✅ Answer Type: {intent.get('answer_type')}")
        print(f"✅ Measures: {intent.get('measures')}")
        print(f"✅ Time: {intent.get('time')}")
        print(f"✅ Geo Hint: {intent.get('geo_hint')}")
        print(f"✅ Needs Clarification: {intent.get('needs_clarification')}")
        print(f"✅ Logs: {result.get('logs', [])}")


if __name__ == "__main__":
    test_intent_node()
