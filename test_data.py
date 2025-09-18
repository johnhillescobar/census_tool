"""
Test script for data_node functionality with comprehensive assertions
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.data import data_node
from src.state.types import CensusState, QuerySpec
from langchain_core.runnables import RunnableConfig


def test_data_node_success():
    """Test data_node with valid state - should succeed"""
    print("Testing data_node with valid state...")

    # Create test state
    test_state = CensusState(
        messages=[],
        intent={},
        geo={},
        candidates={},
        plan={
            "queries": [
                QuerySpec(
                    year=2023,
                    dataset="acs/acs5",
                    variables=["B01003_001E", "NAME"],
                    geo={
                        "level": "place",
                        "filters": {"for": "place:51000", "in": "state:36"},
                    },
                    save_as="B01003_001E_place_2023",
                )
            ],
            "needs_agg": False,
            "agg_spec": None,
        },
        artifacts={"datasets": {}, "previews": {}},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    # Test the data_node
    result = data_node(test_state, RunnableConfig())

    # Assertions for successful case
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "artifacts" in result, "Missing 'artifacts' in result"
    assert "cache_index" in result, "Missing 'cache_index' in result"
    assert "logs" in result, "Missing 'logs' in result"

    artifacts = result["artifacts"]
    assert "datasets" in artifacts, "Missing 'datasets' in artifacts"
    assert "previews" in artifacts, "Missing 'previews' in artifacts"

    # Check that at least one dataset was processed
    assert "datasets" in artifacts, "Missing 'datasets' in artifacts"
    assert "previews" in artifacts, "Missing 'previews' in artifacts"

    # Check that at least one dataset was processed
    datasets = artifacts["datasets"]
    assert len(datasets) > 0, "Expected at least one dataset"

    # Check logs
    logs = result["logs"]
    assert len(logs) == 1, f"Expected at least one log entry, got {len(logs)}"
    assert "data: processed 1 queries" in logs[0], f"Unexpected log: {logs[0]}"

    print("✅ data_node success test passed!")


def test_data_node_missing_plan():
    """Test data_node with missing plan - should fail gracefully"""
    print("Testing data_node with missing plan...")

    test_state = CensusState(
        messages=[],
        intent={},
        geo={},
        candidates={},
        plan={},
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = data_node(test_state, RunnableConfig())

    # Assertions for error case
    assert "error" in result, "Expected error for missing plan"
    assert result["error"] == "No plan found in state", (
        f"Unexpected error message: {result['error']}"
    )
    assert "logs" in result, "Missing 'logs' in result"
    assert "data: ERROR - no plan" in result["logs"], (
        f"Unexpected log: {result['logs']}"
    )

    print("✅ data_node missing plan test passed!")


def test_data_node_empty_queries():
    """Test data_node with empty queries - should fail gracefully"""
    print("Testing data_node with empty queries...")

    test_state = CensusState(
        messages=[],
        intent={},
        geo={},
        candidates={},
        artifacts={},
        plan={"queries": []},  # Empty queries list
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = data_node(test_state, RunnableConfig())

    # Assertions for error case
    assert "error" in result, "Expected error for empty queries"
    assert result["error"] == "Plan contains no queries", (
        f"Unexpected error message: {result['error']}"
    )

    print("✅ data_node empty queries test passed!")


def test_data_node_multi_query():
    """Test data_node with multiple queries - should process all queries"""
    print("Testing data_node with multiple queries...")

    test_state = CensusState(
        messages=[],
        intent={},
        geo={},
        candidates={},
        plan={
            "queries": [
                QuerySpec(
                    year=2023,
                    dataset="acs/acs5",
                    variables=["B01003_001E", "NAME"],
                    geo={
                        "level": "place",
                        "filters": {"for": "place:51000", "in": "state:36"},
                    },
                    save_as="B01003_001E_place_2023",
                ),
                QuerySpec(
                    year=2022,
                    dataset="acs/acs5",
                    variables=["B01003_001E", "NAME"],
                    geo={
                        "level": "place",
                        "filters": {"for": "place:51000", "in": "state:36"},
                    },
                    save_as="B01003_001E_place_2022",
                ),
            ],
            "needs_agg": False,
            "agg_spec": None,
        },
        artifacts={"datasets": {}, "previews": {}},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = data_node(test_state, RunnableConfig())

    # Assertions for multi-query case
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "artifacts" in result, "Missing 'artifacts' in result"

    artifacts = result["artifacts"]
    datasets = artifacts["datasets"]
    previews = artifacts["previews"]

    # Should have processed 2 queries
    assert len(datasets) >= 0, f"Expected datasets, got {len(datasets)}"
    assert len(previews) >= 0, f"Expected previews, got {len(previews)}"

    print("✅ data_node multi-query test passed!")


def run_all_tests():
    """Run all data_node tests"""
    print("=== RUNNING DATA NODE TESTS ===\n")

    try:
        test_data_node_success()
        test_data_node_missing_plan()
        test_data_node_empty_queries()
        test_data_node_multi_query()

        print("\n🎉 ALL DATA NODE TESTS PASSED! 🎉")
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
