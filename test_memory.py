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
    "Mock state (empty for first run)"
    state = {
        "messages": [],
        "profile": {},
        "history": [],
        "cache_index": {},
        "logs": [],
    }

    # Test config
    config = {"user_id": "test_user", "thread_id": "test_thread"}

    print("Testing memory_load_node...")
    result = memory_load_node(state, config)

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


if __name__ == "__main__":
    test_memory_load_node()
