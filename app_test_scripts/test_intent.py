"""
Test script for intent_node
"""

import logging
from src.nodes.intent import intent_node
from src.state.types import CensusState

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_intent_node():
    """Test the intent_node with various inputs"""

    # Test case 1: Valid census question
    test_input = "Population of NYC in 2023"

    # Mock state with the test message
    state = CensusState(
        messages=[{"role": "user", "content": test_input}],
        profile={},
        history=[],
        cache_index={},
        logs=[],
    )

    # Mock config
    config = {"user_id": "test_user", "thread_id": "test_thread"}

    # Test the intent node
    result = intent_node(state, config)

    # Display results for debugging
    intent = result.get("intent", {})
    print(f"✅ Is Census: {intent.get('is_census')}")
    print(f"✅ Answer Type: {intent.get('answer_type')}")
    print(f"✅ Measures: {intent.get('measures')}")
    print(f"✅ Time: {intent.get('time')}")
    print(f"✅ Geo Hint: {intent.get('geo_hint')}")
    print(f"✅ Needs Clarification: {intent.get('needs_clarification')}")
    print(f"✅ Logs: {result.get('logs', [])}")

    # Assertions for pytest
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "intent" in result, "Result should contain intent"
    assert "is_census" in intent, "Intent should contain is_census"
    assert "answer_type" in intent, "Intent should contain answer_type"
    assert "measures" in intent, "Intent should contain measures"
    assert "time" in intent, "Intent should contain time"
    assert "geo_hint" in intent, "Intent should contain geo_hint"
    assert "needs_clarification" in intent, "Intent should contain needs_clarification"


def test_intent_node_non_census():
    """Test the intent_node with non-census question"""

    test_input = "What's 2+2?"

    state = CensusState(
        messages=[{"role": "user", "content": test_input}],
        profile={},
        history=[],
        cache_index={},
        logs=[],
    )

    config = {"user_id": "test_user", "thread_id": "test_thread"}
    result = intent_node(state, config)

    intent = result.get("intent", {})
    print(f"✅ Non-census question - Is Census: {intent.get('is_census')}")

    assert not intent.get("is_census"), (
        "Non-census question should be marked as not census"
    )


if __name__ == "__main__":
    test_intent_node()
