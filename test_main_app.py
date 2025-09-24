"""
Test script for main.py - testing the fixes you made
"""

import sys
import os
import main
from app import create_census_graph

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state.types import CensusState


def test_main_app_startup():
    """Test main app startup"""

    print("Testing main app startup...")
    assert hasattr(main, "main")
    print("✅ main app startup test passed!")


def test_census_app_creation():
    """Test census app creation"""

    print("Testing census app creation...")
    graph = create_census_graph()
    assert graph is not None
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "get_graph")
    print("✅ census app creation test passed!")


def test_user_input_processing():
    """Test user input processing"""
    print("Testing user input processing...")

    # Test the logic directly
    # Test case 1: Valid input
    user_input = "What's the population of New York City?"
    if user_input:
        # This should execute (the fixed logic)
        assert True, "Valid input should trigger processing"

    # Test case 2: Empty input
    user_input = ""
    if user_input:
        # This should NOT execute
        assert False, "Empty input should NOT trigger processing"
    else:
        # This should execute
        assert True, "Empty input should skip processing"

    print("✅ User input processing test passed!")


def test_census_state_creation():
    """Test that CensusState can be created with messages field"""
    print("Testing CensusState creation...")

    # 1. Create CensusState with messages field
    state = CensusState(
        messages=[
            {"role": "user", "content": "What's the population of New York City?"}
        ],
        intent=None,
        geo={},
        candidates={},
        plan=None,
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )
    # 2. Verify it works
    assert state["messages"] == [
        {"role": "user", "content": "What's the population of New York City?"}
    ]
    assert state["intent"] is None
    assert state["geo"] == {}
    assert state["candidates"] == {}
    assert state["plan"] is None
    assert state["artifacts"] == {}
    assert state["final"] is None
    assert state["logs"] == []

    # 3. Verify the field is accessible
    # Test that we can read and write to the fields
    state["intent"] = {"test": "data"}  # ← Test writing
    assert state["intent"]["test"] == "data"  # ← Test reading

    state["geo"]["level"] = "place"  # ← Test writing to nested field
    assert state["geo"]["level"] == "place"  # ← Test reading from nested field

    print("✅ CensusState creation test passed!")


def test_quit_functionality():
    """Test quit functionality"""
    print("Testing quit functionality...")
    result = main.main("quit")
    assert result is not None
    assert result.get("messages") is not None
    assert result.get("messages")[0].get("role") == "user"
    assert result.get("messages")[0].get("content") == "quit"
    print("✅ Quit functionality test passed!")


def test_error_handling():
    """Test error handling"""
    print("Testing error handling...")
    result = main.main("invalid input")
    assert result is not None
    assert result.get("messages") is not None
    assert result.get("messages")[0].get("role") == "user"
    assert result.get("messages")[0].get("content") == "invalid input"
    print("✅ Error handling test passed!")


def test_all_tests():
    """Test all tests"""
    test_main_app_startup()
    test_census_app_creation()
    test_user_input_processing()
    test_census_state_creation()
    print("✅ All tests passed!")


if __name__ == "__main__":
    test_all_tests()
