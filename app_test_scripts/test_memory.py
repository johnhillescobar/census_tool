"""
Test script for memory_load_node
"""

import logging
from langchain_core.runnables import RunnableConfig
from src.workflows.memory import memory_load_node
from src.state.types import CensusState, WorkflowArtifactsState

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Test the memory_load_node
def test_memory_load_node():
    """Test the memory_load_node function"""
    # Mock state (empty for first run)
    state = CensusState(
        messages=[],
        original_query=None,
        intent=None,
        geo={},
        candidates={},
        plan=None,
        artifacts=WorkflowArtifactsState(),
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    # Test config - FIXED: user_id should be nested under "configurable"
    config: RunnableConfig = {
        "configurable": {"user_id": "test_user", "thread_id": "test_thread"}
    }

    # Test the function
    result = memory_load_node(state, config)

    # Display results for debugging
    print("Result:")
    print(f"Profile: {result.get('profile', {})}")
    print(f"History: {len(result.get('history', []))}")
    ci = result.get("cache_index")
    cache_len = len(ci) if isinstance(ci, dict) else (len(ci.root) if ci else 0)
    print(f"Cache Index entries: {cache_len}")
    print(f"Logs: {result.get('logs', [])}")

    # Assertions for pytest
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "profile" in result, "Result should contain profile"
    assert "history" in result, "Result should contain history"
    assert "cache_index" in result, "Result should contain cache_index"
    assert "logs" in result, "Result should contain logs"

    print("✅ Test memory load node passed")


if __name__ == "__main__":
    test_memory_load_node()
