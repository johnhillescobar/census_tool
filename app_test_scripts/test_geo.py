"""
Test script for geo_node
"""

import logging
from src.nodes.geo import geo_node
from src.state.types import CensusState

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_geo_node():
    """Test the geo_node function"""

    # Test cases with expected results
    test_cases = [
        {
            "geo_hint": "nyc",
            "expected_level": "place",
            "expected_filters": {"for": "place:51000", "in": "state:36"},
            "should_error": False,
            "description": "Should resolve to NYC place",
        },
        {
            "geo_hint": "california",
            "expected_level": "state",
            "expected_filters": {"for": "state:06"},
            "should_error": False,
            "description": "Should resolve to California state",
        },
        {
            "geo_hint": "nation",
            "expected_level": "nation",
            "expected_filters": {"for": "us:1"},
            "should_error": False,
            "description": "Should resolve to US nation",
        },
        {
            "geo_hint": "",
            "expected_level": "place",
            "expected_filters": {"for": "place:51000", "in": "state:36"},
            "should_error": False,
            "description": "Should use default NYC",
        },
        {
            "geo_hint": "tract",
            "expected_level": None,
            "expected_filters": None,
            "should_error": True,
            "description": "Should return unsupported error",
        },
        {
            "geo_hint": "unknown place",
            "expected_level": "place",
            "expected_filters": {"for": "place:51000", "in": "state:36"},
            "should_error": False,
            "description": "Should fallback to default",
        },
    ]

    for test_case in test_cases:
        geo_hint = test_case["geo_hint"]
        description = test_case["description"]

        print(f"\n--- Test: '{geo_hint}' ({description}) ---")

        # Mock state
        state = CensusState(
            intent={
                "geo_hint": geo_hint,
                "is_census": True,
                "answer_type": "single",
                "measures": ["population"],
                "time": {"year": 2023},
                "needs_clarification": False,
            },
            profile={"default_geo": {}},
            messages=[],
            history=[],
            cache_index={},
            logs=[],
        )

        config = {"user_id": "test_user", "thread_id": "test_thread"}

        result = geo_node(state, config)

        # Basic assertions
        assert isinstance(result, dict), (
            f"Result should be a dictionary, got {type(result)}"
        )
        assert "logs" in result, "Result should contain logs"
        assert isinstance(result["logs"], list), "Logs should be a list"
        assert len(result["logs"]) > 0, "Should have at least one log entry"

        if test_case["should_error"]:
            # Assert error case
            assert "error" in result, f"Expected error for '{geo_hint}' but got success"
            assert isinstance(result["error"], str), "Error should be a string"
            assert len(result["error"]) > 0, "Error message should not be empty"
            print(f"❌ Error: {result['error']}")
        else:
            # Assert success case
            assert "error" not in result, (
                f"Expected success for '{geo_hint}' but got error: {result.get('error')}"
            )
            assert "geo" in result, "Result should contain geo information"

            geo = result["geo"]
            assert isinstance(geo, dict), "Geo should be a dictionary"

            # Assert expected level
            actual_level = geo.get("level")
            expected_level = test_case["expected_level"]
            assert actual_level == expected_level, (
                f"Expected level '{expected_level}', got '{actual_level}'"
            )

            # Assert expected filters
            actual_filters = geo.get("filters")
            expected_filters = test_case["expected_filters"]
            assert actual_filters == expected_filters, (
                f"Expected filters {expected_filters}, got {actual_filters}"
            )

            # Assert required fields
            assert "note" in geo, "Geo should contain a note"
            assert isinstance(geo["note"], str), "Note should be a string"
            assert len(geo["note"]) > 0, "Note should not be empty"

            print(f"✅ Level: {actual_level}")
            print(f"✅ Filters: {actual_filters}")
            print(f"✅ Note: {geo.get('note')}")

        print(f"📝 Logs: {result.get('logs', [])}")

    print("\n🎉 All geo_node tests passed!")


def test_geo_node_edge_cases():
    """Test edge cases for geo_node"""
    
    # Test with missing intent
    print("\n--- Test: Missing intent ---")
    state_no_intent = CensusState(
        profile={},
        messages=[],
        history=[],
        cache_index={},
        logs=[],
    )

    result = geo_node(state_no_intent, {"user_id": "test_user"})
    assert "error" in result, "Should return error when intent is missing"
    assert "logs" in result, "Should have logs even on error"
    print(f"✅ Correctly handled missing intent: {result['error']}")

    # Test with profile default geo
    print("\n--- Test: Profile default geo ---")
    state_with_default = {
        "intent": {"geo_hint": ""},
        "profile": {
            "default_geo": {
                "level": "state",
                "filters": {"for": "state:06"},
                "note": "User's default",
            }
        },
        "messages": [],
        "history": [],
        "cache_index": {},
        "logs": [],
    }

    result = geo_node(state_with_default, {"user_id": "test_user"})
    assert "error" not in result, "Should not error with profile default"
    assert result["geo"]["level"] == "state", "Should use profile default"
    print(f"✅ Correctly used profile default: {result['geo']}")


if __name__ == "__main__":
    test_geo_node()
    test_geo_node_edge_cases()
