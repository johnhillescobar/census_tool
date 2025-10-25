"""
Test script for memory_utils.py - testing the fixes you made
"""

import sys
import os
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.memory_utils import (
    build_history_record,
    update_profile,
    prune_history_by_age,
    enforce_retention_policies,
)


def test_build_history_record():
    """Test history record building"""
    print("Testing build_history_record...")

    # Test case 1: Basic functionality with valid inputs
    messages = [
        {"role": "user", "content": "What is the population of the United States?"}
    ]
    final = {"type": "number", "value": "8.4 million"}
    intent = {"type": "population_query", "location": "NYC"}
    geo = {"level": "place", "name": "New York City"}
    plan = {
        "queries": [
            {"year": "2020", "dataset": "population"},
            {"year": "2019", "dataset": "population"},
        ]
    }

    user_id = "test_user"

    # Call the function
    result = build_history_record(messages, final, intent, geo, plan, user_id)

    # Test the result
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "timestamp" in result, "Result should contain timestamp"
    assert result["user_id"] == "test_user", "User ID should match"
    assert result["question"] == "What is the population of the United States?", (
        "Question should be extracted"
    )
    assert result["intent"] == intent, "Intent should be preserved"
    assert result["geo"] == geo, "Geo should be preserved"
    assert (
        "2 queries for years ['2020', '2019'] using ['population', 'population']"
        in result["plan_summary"]
    ), "Plan summary should be correct"
    assert result["answer_type"] == "number", "Answer type should be extracted"
    assert result["success"], "Success should be True when no error"

    print("✅ build_history_record test passed!")


def test_update_profile():
    """Test profile updating logic"""
    print("Testing update_profile...")

    # Test case 1: Basic profile update with successful query
    profile = {}
    intent = {
        "type": "population_query",
        "dataset": "population",
        "measures": ["population"],
    }
    geo = {"level": "place", "name": "New York City", "display_name": "NYC"}

    final = {"type": "number", "value": "8.4 million", "variable": "B01003_001E"}

    # Call the function
    result = update_profile(profile, intent, geo, final)

    # Test the result
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result["default_geo"] == geo, "Default geo should be updated"
    assert result["last_geo"] == "NYC", "Last geo should be updated"
    assert result["preferred_dataset"] == "population", (
        "Preferred dataset should be updated"
    )
    assert "var_aliases" in result, "Variable aliases should be present"
    assert result["var_aliases"]["population"] == "B01003_001E", (
        "Variable alias should be set"
    )
    assert "usage_stats" in result, "Usage stats should be present"
    assert result["usage_stats"]["total_queries"] == 1, "Total queries should be 1"
    assert result["usage_stats"]["success_queries"] == 1, "Success queries should be 1"
    assert result["usage_stats"]["last_query_date"] is not None, (
        "Last query date should be set"
    )

    print("✅ Basic profile update test passed!")


def test_prune_history_by_age():
    """Test retention policy enforcement"""
    print("Testing prune_history_by_age...")

    # Test case 1: Basic functionality with old entries
    now = datetime.now()
    old_date = (now - timedelta(days=10)).isoformat()
    new_date = (now - timedelta(days=3)).isoformat()  # 3 days old instead of 5

    history = [
        {"timestamp": old_date, "question": "Old question", "user_id": "user1"},
        {"timestamp": new_date, "question": "New question", "user_id": "user2"},
        {
            "timestamp": now.isoformat(),
            "question": "Current question",
            "user_id": "user3",
        },
    ]

    # Test with 5-day retention (should keep only 2-day old and current entries)
    result = prune_history_by_age(history, 5)

    # Test the result
    assert isinstance(result, list), "Result should be a list"
    assert len(result) == 2, "Result should contain 2 entries"
    assert result[0]["question"] == "New question", "New question should be kept"
    assert result[1]["question"] == "Current question", (
        "Current question should be kept"
    )

    print("✅ prune_history_by_age test passed!")

    # Test case 2: Empty history
    result = prune_history_by_age([], 5)
    assert result == [], "Empty history should return empty list"

    print("✅ Empty history test passed!")

    # Test case 3: All entries are old
    old_history = [
        {"timestamp": old_date, "question": "Very old question", "user_id": "user1"}
    ]
    result = prune_history_by_age(old_history, 5)
    assert result == [], "All old entries should be removed"

    print("✅ All old entries test passed!")


def test_enforce_retention_policies():
    """Test retention policy enforcement"""
    # Create test data
    test_profile = {
        "user_id": "test_user",
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
                "question": "Old question",
            },
            {
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "question": "New question",
            },
        ],
    }

    test_cache_index = {
        "cache1": {
            "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
            "file_path": "/tmp/old.csv",
        },
        "cache2": {
            "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
            "file_path": "/tmp/new.csv",
        },
    }

    # Mock file operations
    with (
        patch("src.utils.memory_utils.load_json_file") as mock_load,
        patch("src.utils.memory_utils.save_json_file") as mock_save,
        patch("src.utils.memory_utils.prune_cache_by_age") as mock_prune_cache,
    ):
        # Set up mocks
        mock_load.side_effect = [test_profile, test_cache_index]
        mock_prune_cache.return_value = {"cache2": test_cache_index["cache2"]}

        # Mock prune_history_by_age to return a different length (to trigger save)
        with patch("src.utils.memory_utils.prune_history_by_age") as mock_prune_history:
            mock_prune_history.return_value = [test_profile["history"][1]]

        # Call the function
        profile_file = Path("/tmp/test_profile.json")
        cache_file = Path("/tmp/test_cache.json")
        user_id = "test_user"

        enforce_retention_policies(profile_file, cache_file, user_id)

        # Test that functions were called correctly
        assert mock_load.call_count == 2, "Should load profile and cache files"
        assert mock_save.call_count >= 1, "Should save at least one file"
        assert mock_prune_cache.called, "Should call prune_cache_by_age"

        print("✅ Basic retention enforcement test passed!")

    # Test case 2: Error handling
    with patch("src.utils.memory_utils.load_json_file") as mock_load:
        mock_load.side_effect = Exception("File not found")

        # Should not raise exception
        try:
            enforce_retention_policies(
                Path("/tmp/missing.json"), Path("/tmp/missing.json"), "test_user"
            )
            print("✅ Error handling test passed!")
        except Exception:
            assert False, "Function should handle errors gracefully"

    print("✅ All enforce_retention_policies tests passed!")


if __name__ == "__main__":
    test_build_history_record()
    test_update_profile()
    test_prune_history_by_age()
    test_enforce_retention_policies()
    print("✅ All tests passed!")
