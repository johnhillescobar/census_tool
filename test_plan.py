"""
Test script for plan_node functionality with comprehensive assertions
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.retrieve import plan_node
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig


def test_plan_node_success():
    """Test plan_node with valid state - should succeed"""
    print("Testing plan_node with valid state...")

    # Create test state
    test_state = CensusState(
        messages=[],
        intent={
            "is_census": True,
            "answer_type": "single",
            "measures": ["population"],
            "time": {"year": 2023},
            "geo_hint": "NYC",
            "needs_clarification": False,
        },
        geo={"level": "place", "filters": {"for": "place:51000", "in": "state:36"}},
        candidates={
            "variables": [
                {
                    "var": "B01003_001E",
                    "label": "Total population",
                    "concept": "Total population",
                    "dataset": "acs/acs5",
                    "years_available": [2023],
                    "score": 0.95,
                }
            ],
            "years": [2023],
        },
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    # Test the plan_node
    result = plan_node(test_state, RunnableConfig())

    # Assertions for successful case
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "plan" in result, "Missing 'plan' in result"
    assert "logs" in result, "Missing 'logs' in result"

    plan = result["plan"]
    assert "queries" in plan, "Missing 'queries' in plan"
    assert "needs_agg" in plan, "Missing 'needs_agg' in plan"
    assert "agg_spec" in plan, "Missing 'agg_spec' in plan"

    queries = plan["queries"]
    assert len(queries) == 1, f"Expected 1 query, got {len(queries)}"

    query = queries[0]
    required_keys = ["year", "dataset", "variables", "geo", "save_as"]
    for key in required_keys:
        assert key in query, f"Missing required key '{key}' in QuerySpec"

    # Validate specific values
    assert query["year"] == 2023, f"Expected year 2023, got {query['year']}"
    assert query["dataset"] == "acs/acs5", (
        f"Expected dataset 'acs/acs5', got {query['dataset']}"
    )
    assert "B01003_001E" in query["variables"], (
        "Expected variable 'B01003_001E' in variables"
    )
    assert "NAME" in query["variables"], "Expected 'NAME' variable in variables"
    assert len(query["variables"]) == 2, (
        f"Expected 2 variables, got {len(query['variables'])}"
    )
    assert query["geo"] == test_state["geo"], "Geo should match input geo"
    assert query["save_as"] == "B01003_001E_place_2023", (
        f"Unexpected save_as: {query['save_as']}"
    )

    # Validate plan structure
    assert plan["needs_agg"] == False, "needs_agg should be False"
    assert plan["agg_spec"] is None, "agg_spec should be None"

    # Validate logs
    logs = result["logs"]
    assert len(logs) == 1, f"Expected 1 log entry, got {len(logs)}"
    assert "plan: built 1 query specs" in logs[0], f"Unexpected log: {logs[0]}"

    print("✅ plan_node success test passed!")


def test_plan_node_missing_intent():
    """Test plan_node with missing intent - should fail gracefully"""
    print("Testing plan_node with missing intent...")

    test_state = CensusState(
        messages=[],
        intent=None,  # Missing intent
        geo={"level": "place", "filters": {"for": "place:51000", "in": "state:36"}},
        candidates={"variables": [], "years": []},
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = plan_node(test_state, RunnableConfig())

    # Assertions for error case
    assert "error" in result, "Expected error for missing intent"
    assert result["error"] == "No intent found in state", (
        f"Unexpected error message: {result['error']}"
    )
    assert "logs" in result, "Missing 'logs' in result"
    assert "plan: ERROR - no intent" in result["logs"], (
        f"Unexpected log: {result['logs']}"
    )

    print("✅ plan_node missing intent test passed!")


def test_plan_node_missing_geo():
    """Test plan_node with missing geo - should fail gracefully"""
    print("Testing plan_node with missing geo...")

    test_state = CensusState(
        messages=[],
        intent={"is_census": True, "measures": ["population"]},
        geo={},  # Empty geo
        candidates={"variables": [], "years": []},
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = plan_node(test_state, RunnableConfig())

    # Assertions for error case
    assert "error" in result, "Expected error for missing geo"
    assert result["error"] == "No geo found in state", (
        f"Unexpected error message: {result['error']}"
    )
    assert "plan: ERROR - no geo" in result["logs"], f"Unexpected log: {result['logs']}"

    print("✅ plan_node missing geo test passed!")


def test_plan_node_missing_candidates():
    """Test plan_node with missing candidates - should fail gracefully"""
    print("Testing plan_node with missing candidates...")

    test_state = CensusState(
        messages=[],
        intent={"is_census": True, "measures": ["population"]},
        geo={"level": "place", "filters": {"for": "place:51000", "in": "state:36"}},
        candidates={},  # Empty candidates
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = plan_node(test_state, RunnableConfig())

    # Assertions for error case
    assert "error" in result, "Expected error for missing candidates"
    assert result["error"] == "No candidates found in state", (
        f"Unexpected error message: {result['error']}"
    )
    assert "plan: ERROR - no candidates" in result["logs"], (
        f"Unexpected log: {result['logs']}"
    )

    print("✅ plan_node missing candidates test passed!")


def test_plan_node_low_confidence():
    """Test plan_node with low confidence candidate - should fail gracefully"""
    print("Testing plan_node with low confidence...")

    test_state = CensusState(
        messages=[],
        intent={"is_census": True, "measures": ["population"]},
        geo={"level": "place", "filters": {"for": "place:51000", "in": "state:36"}},
        candidates={
            "variables": [
                {
                    "var": "B01003_001E",
                    "label": "Total population",
                    "concept": "Total population",
                    "dataset": "acs/acs5",
                    "years_available": [2023],
                    "score": 0.3,  # Low confidence
                }
            ],
            "years": [2023],
        },
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = plan_node(test_state, RunnableConfig())

    # Assertions for low confidence case
    assert "error" in result, "Expected error for low confidence"
    assert "confidence" in result["error"].lower(), (
        f"Error should mention confidence: {result['error']}"
    )
    assert "plan: confidence 0.30 below threshold" in result["logs"], (
        f"Unexpected log: {result['logs']}"
    )

    print("✅ plan_node low confidence test passed!")


def test_plan_node_multi_year():
    """Test plan_node with multiple years - should create multiple queries"""
    print("Testing plan_node with multiple years...")

    test_state = CensusState(
        messages=[],
        intent={
            "is_census": True,
            "answer_type": "series",
            "measures": ["population"],
            "time": {"start_year": 2020, "end_year": 2023},
            "geo_hint": "NYC",
            "needs_clarification": False,
        },
        geo={"level": "place", "filters": {"for": "place:51000", "in": "state:36"}},
        candidates={
            "variables": [
                {
                    "var": "B01003_001E",
                    "label": "Total population",
                    "concept": "Total population",
                    "dataset": "acs/acs5",
                    "years_available": [2020, 2021, 2022, 2023],
                    "score": 0.95,
                }
            ],
            "years": [2020, 2021, 2022, 2023],
        },
        artifacts={},
        final=None,
        logs=[],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )

    result = plan_node(test_state, RunnableConfig())

    # Assertions for multi-year case
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "plan" in result, "Missing 'plan' in result"

    queries = result["plan"]["queries"]
    assert len(queries) == 4, f"Expected 4 queries for 4 years, got {len(queries)}"

    # Check each query has correct year
    years = [query["year"] for query in queries]
    assert sorted(years) == [2020, 2021, 2022, 2023], f"Unexpected years: {years}"

    # Check save_as filenames are unique
    save_as_names = [query["save_as"] for query in queries]
    assert len(set(save_as_names)) == 4, (
        f"Save_as names should be unique: {save_as_names}"
    )

    print("✅ plan_node multi-year test passed!")


def run_all_tests():
    """Run all plan_node tests"""
    print("=== RUNNING PLAN NODE TESTS ===\n")

    try:
        test_plan_node_success()
        test_plan_node_missing_intent()
        test_plan_node_missing_geo()
        test_plan_node_missing_candidates()
        test_plan_node_low_confidence()
        test_plan_node_multi_year()

        print("\n🎉 ALL PLAN NODE TESTS PASSED! 🎉")
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
