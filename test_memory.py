"""
Test script for memory_load_node
"""

import logging
from pathlib import Path
from src.nodes.memory import memory_load_node

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Test the memory_load_node
def test_memory_load_node():
    """Test the memory_load_node function"""
    # Mock state (empty for first run)
    state = {
        "messages": [],
        "profile": {},
        "history": [],
        "cache_index": {},
        "logs": [],
    }

    # Test config
    config = {"user_id": "test_user", "thread_id": "test_thread"}

    # Test the function
    result = memory_load_node(state, config)

    # Display results for debugging
    print("Result:")
    print(f"Profile: {result.get('profile', {})}")
    print(f"History: {len(result.get('history', []))}")
    print(f"Cache Index: {len(result.get('cache_index', []))}")
    print(f"Logs: {result.get('logs', [])}")

    # Check if files were created
    memory_dir = Path("memory")
    profile_file = memory_dir / "user_test_user.json"
    cache_file = memory_dir / "cache_index_test_user.json"

    print("\nFiles created:")
    print(f"Profile file exists: {profile_file.exists()}")
    print(f"Cache file exists: {cache_file.exists()}")

    # Assertions for pytest
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "profile" in result, "Result should contain profile"
    assert "history" in result, "Result should contain history"
    assert "cache_index" in result, "Result should contain cache_index"
    assert "logs" in result, "Result should contain logs"
    assert profile_file.exists(), "Profile file should be created"
    assert cache_file.exists(), "Cache file should be created"


if __name__ == "__main__":
    test_memory_load_node()
