"""
Test script for retrieve_node and related utility functions
Includes both print statements and assertions for GitHub Actions CI
"""

import logging
from unittest.mock import Mock, patch
from src.nodes.retrieve import retrieve_node
from src.state.types import CensusState
from src.utils.retrieval_utils import (
    process_chroma_results,
    calculate_confidence_score,
    get_fallback_candidates,
)
from src.utils.text_utils import build_retrieval_query, add_measure_synonyms

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_add_measure_synonyms():
    """Test the add_measure_synonyms function"""
    print("\n--- Testing add_measure_synonyms ---")

    # Test case 1: Population synonyms
    result = add_measure_synonyms(["population"])
    print(f"Input: ['population'] -> Result: {result}")
    assert "people" in result, "Should include 'people' synonym"
    assert "residents" in result, "Should include 'residents' synonym"
    assert "inhabitants" in result, "Should include 'inhabitants' synonym"
    print("✅ Population synonyms test passed")

    # Test case 2: Hispanic synonyms
    result = add_measure_synonyms(["hispanic"])
    print(f"Input: ['hispanic'] -> Result: {result}")
    assert "latino" in result, "Should include 'latino' synonym"
    assert "latina" in result, "Should include 'latina' synonym"
    print("✅ Hispanic synonyms test passed")

    # Test case 3: Multiple measures
    result = add_measure_synonyms(["income", "population"])
    print(f"Input: ['income', 'population'] -> Result: {result}")
    assert "earnings" in result, "Should include 'earnings' synonym"
    assert "people" in result, "Should include 'people' synonym"
    print("✅ Multiple measures synonyms test passed")

    # Test case 4: Unknown measure (no synonyms)
    result = add_measure_synonyms(["unknown_measure"])
    print(f"Input: ['unknown_measure'] -> Result: {result}")
    assert result == ["unknown_measure"], "Should return original list unchanged"
    print("✅ Unknown measure test passed")

    print("�� All add_measure_synonyms tests passed!\n")


def test_build_retrieval_query():
    """Test the build_retrieval_query function"""
    print("\n--- Testing build_retrieval_query ---")

    # Test case 1: Basic population query
    intent = {
        "measures": ["population"],
        "answer_type": "single",
        "time": {"year": 2023},
    }
    profile = {"preferred_dataset": "acs/acs5"}

    result = build_retrieval_query(intent, profile)
    print(f"Basic query: '{result}'")
    assert "population" in result, "Should include population measure"
    assert "people" in result, "Should include population synonym"
    assert "year 2023" in result, "Should include year hint"
    assert "dataset:acs/acs5" in result, "Should include dataset hint"
    print("✅ Basic population query test passed")

    # Test case 2: Complex query with var_aliases
    intent = {
        "measures": ["income", "hispanic"],
        "answer_type": "series",
        "time": {"start_year": 2020, "end_year": 2023},
    }
    profile = {
        "preferred_dataset": "acs/acs5",
        "var_aliases": {"income hispanic": "B19013I_001E"},
    }

    result = build_retrieval_query(intent, profile)
    print(f"Complex query: '{result}'")
    assert result.startswith("B19013I_001E"), "Should start with var_alias code"
    assert "income" in result, "Should include income measure"
    assert "latino" in result, "Should include hispanic synonym"
    assert "over time" in result, "Should include series hints"
    assert "years 2020 to 2023" in result, "Should include year range"
    print("✅ Complex query with var_aliases test passed")

    # Test case 3: Table query with defaults
    intent = {"measures": ["population"], "answer_type": "table", "time": {}}
    profile = {}

    result = build_retrieval_query(intent, profile)
    print(f"Table query: '{result}'")
    assert "population" in result, "Should include population measure"
    assert "breakdown" in result, "Should include table hints"
    assert "dataset:acs/acs5" in result, "Should use default dataset"
    print("✅ Table query test passed")

    print("🎉 All build_retrieval_query tests passed!\n")


def test_calculate_confidence_score():
    """Test the calculate_confidence_score function"""
    print("\n--- Testing calculate_confidence_score ---")

    # Test case 1: Population variable with boosts
    metadata = {
        "label": "Total Population",
        "concept": "Population estimates",
        "var": "B01003_001E",
        "dataset": "acs/acs5",
    }

    result = calculate_confidence_score(0.5, metadata, ["population"], "acs/acs5")
    print(f"Population variable score: {result}")
    assert result > 0.5, "Should have positive boost"
    assert result <= 1.0, "Should not exceed 1.0"
    print("✅ Population variable scoring test passed")

    # Test case 2: Income variable with boosts
    metadata = {
        "label": "Median Household Income",
        "concept": "Income estimates",
        "var": "B19013_001E",
        "dataset": "acs/acs5",
    }

    result = calculate_confidence_score(0.3, metadata, ["income"], "acs/acs5")
    print(f"Income variable score: {result}")
    assert result > 0.3, "Should have positive boost"
    assert result <= 1.0, "Should not exceed 1.0"
    print("✅ Income variable scoring test passed")

    # Test case 3: Variable with no relevant boosts
    metadata = {
        "label": "Some other variable",
        "concept": "Other estimates",
        "var": "B12345_002E",
        "dataset": "acs/acs1",
    }

    result = calculate_confidence_score(0.8, metadata, ["population"], "acs/acs5")
    print(f"Non-matching variable score: {result}")
    assert result == 0.8, "Should have no boost for non-matching variable"
    print("✅ Non-matching variable scoring test passed")

    print("🎉 All calculate_confidence_score tests passed!\n")


def test_get_fallback_candidates():
    """Test the get_fallback_candidates function"""
    print("\n--- Testing get_fallback_candidates ---")

    # Test case 1: Population fallback
    result = get_fallback_candidates(["population"], "acs/acs5")
    print(f"Population fallback result: {result is not None}")
    assert result is not None, "Should find population fallback"
    assert "variables" in result, "Should have variables key"
    assert len(result["variables"]) > 0, "Should have at least one fallback variable"
    assert result["variables"][0]["var"] == "B01003_001E", (
        "Should use correct population variable"
    )
    print("✅ Population fallback test passed")

    # Test case 2: Hispanic income fallback
    result = get_fallback_candidates(["hispanic_median_income"], "acs/acs5")
    print(f"Hispanic income fallback result: {result is not None}")
    assert result is not None, "Should find hispanic income fallback"
    assert result["variables"][0]["var"] == "B19013I_001E", (
        "Should use correct hispanic income variable"
    )
    print("✅ Hispanic income fallback test passed")

    # Test case 3: Unknown measure (no fallback)
    result = get_fallback_candidates(["unknown_measure"], "acs/acs5")
    print(f"Unknown measure fallback result: {result is not None}")
    assert result is None, "Should not find fallback for unknown measure"
    print("✅ Unknown measure fallback test passed")

    print("🎉 All get_fallback_candidates tests passed!\n")


def test_process_chroma_results():
    """Test the process_chroma_results function with mock data"""
    print("\n--- Testing process_chroma_results ---")

    # Mock Chroma results
    mock_results = {
        "documents": [
            [
                "Total population estimate for all people",
                "Median household income in the past 12 months",
            ]
        ],
        "metadatas": [
            [
                {
                    "var": "B01003_001E",
                    "label": "Total Population",
                    "concept": "Population estimates",
                    "universe": "All people",
                    "dataset": "acs/acs5",
                    "years_available": "2020,2021,2022,2023",
                },
                {
                    "var": "B19013_001E",
                    "label": "Median Household Income",
                    "concept": "Income estimates",
                    "universe": "Households",
                    "dataset": "acs/acs5",
                    "years_available": "2020,2021,2022,2023",
                },
            ]
        ],
        "distances": [[0.2, 0.4]],
    }

    # Test case 1: Population query with year filter
    result = process_chroma_results(
        mock_results, ["population"], {"year": 2023}, "acs/acs5"
    )

    print(f"Population query - Variables found: {len(result.get('variables', []))}")
    assert "variables" in result, "Should have variables key"
    assert "years" in result, "Should have years key"
    assert "notes" in result, "Should have notes key"
    assert len(result["variables"]) > 0, "Should find population variables"
    assert 2023 in result["years"], "Should include requested year"
    assert result["variables"][0]["var"] == "B01003_001E", (
        "Should prioritize population variable"
    )
    print("✅ Population query processing test passed")

    # Test case 2: Income query with year range
    result = process_chroma_results(
        mock_results, ["income"], {"start_year": 2020, "end_year": 2023}, "acs/acs5"
    )

    print(f"Income query - Variables found: {len(result.get('variables', []))}")
    assert len(result["variables"]) > 0, "Should find income variables"
    assert all(2020 <= year <= 2023 for year in result["years"]), (
        "Should filter years correctly"
    )
    print("✅ Income query processing test passed")

    print("🎉 All process_chroma_results tests passed!\n")


@patch("src.nodes.retrieve.initialize_chroma_client")
@patch("src.nodes.retrieve.get_chroma_collection")
def test_retrieve_node_success(mock_get_collection, mock_init_client):
    """Test retrieve_node with successful Chroma query"""
    print("\n--- Testing retrieve_node (success case) ---")

    # Mock Chroma client and collection
    mock_client = Mock()
    mock_collection = Mock()
    mock_init_client.return_value = mock_client
    mock_get_collection.return_value = mock_collection

    # Mock Chroma query results
    mock_collection.query.return_value = {
        "documents": [["Total population estimate"]],
        "metadatas": [
            [
                {
                    "var": "B01003_001E",
                    "label": "Total Population",
                    "concept": "Population estimates",
                    "universe": "All people",
                    "dataset": "acs/acs5",
                    "years_available": "2023",
                }
            ]
        ],
        "distances": [[0.1]],
    }

    # Test state
    state = CensusState(
        intent={
            "measures": ["population"],
            "answer_type": "single",
            "time": {"year": 2023},
        },
        profile={"preferred_dataset": "acs/acs5"},
        messages=[],
        history=[],
        cache_index={},
        logs=[],
    )

    config = {"user_id": "test_user", "thread_id": "test_thread"}

    result = retrieve_node(state, config)

    print(f"Result type: {type(result)}")
    print(f"Has candidates: {'candidates' in result}")
    print(f"Has error: {'error' in result}")

    assert isinstance(result, dict), "Result should be a dictionary"
    assert "candidates" in result, "Should have candidates key"
    assert "logs" in result, "Should have logs key"
    assert "error" not in result, "Should not have error for successful case"
    assert len(result["logs"]) > 0, "Should have log entries"

    candidates = result["candidates"]
    assert "variables" in candidates, "Candidates should have variables"
    assert len(candidates["variables"]) > 0, "Should find at least one variable"

    print("✅ retrieve_node success test passed\n")


@patch("src.nodes.retrieve.initialize_chroma_client")
@patch("src.nodes.retrieve.get_chroma_collection")
def test_retrieve_node_fallback(mock_get_collection, mock_init_client):
    """Test retrieve_node fallback behavior"""
    print("\n--- Testing retrieve_node (fallback case) ---")

    # Mock Chroma client and collection
    mock_client = Mock()
    mock_collection = Mock()
    mock_init_client.return_value = mock_client
    mock_get_collection.return_value = mock_collection

    # Mock empty Chroma query results (triggers fallback)
    mock_collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    # Test state
    state = CensusState(
        intent={
            "measures": ["population"],
            "answer_type": "single",
            "time": {"year": 2023},
        },
        profile={"preferred_dataset": "acs/acs5"},
        messages=[],
        history=[],
        cache_index={},
        logs=[],
    )

    config = {"user_id": "test_user", "thread_id": "test_thread"}

    result = retrieve_node(state, config)

    print(f"Used fallback: {'retrieve: used fallback' in result.get('logs', [])}")
    print(f"Has candidates: {'candidates' in result}")
    print(f"Has error: {'error' in result}")

    assert isinstance(result, dict), "Result should be a dictionary"
    assert "candidates" in result, "Should have candidates from fallback"
    assert "logs" in result, "Should have logs"
    assert "error" not in result, "Should not have error for fallback case"
    assert any("fallback" in log for log in result["logs"]), "Should log fallback usage"

    candidates = result["candidates"]
    assert "variables" in candidates, "Fallback candidates should have variables"
    assert len(candidates["variables"]) > 0, "Should have fallback variables"

    print("✅ retrieve_node fallback test passed\n")


def test_retrieve_node_error_cases():
    """Test retrieve_node error handling"""
    print("\n--- Testing retrieve_node (error cases) ---")

    # Test case 1: No intent
    state_no_intent = CensusState(
        profile={},
        messages=[],
        history=[],
        cache_index={},
        logs=[],
    )

    config = {"user_id": "test_user", "thread_id": "test_thread"}

    result = retrieve_node(state_no_intent, config)

    print("Test 1 - No intent:")
    print(f"Has error: {'error' in result}")
    print(f"Error message: {result.get('error', 'None')}")

    assert isinstance(result, dict), "Result should be a dictionary"
    assert "error" in result, "Should have error for missing intent"
    assert "logs" in result, "Should have logs even on error"
    assert result["error"] == "No intent found in state", (
        "Should have correct error message"
    )

    print("✅ retrieve_node error handling test passed\n")


def main():
    """Run all tests"""
    print("🧪 Starting retrieve_node test suite...")
    print("=" * 60)

    try:
        # Test utility functions
        test_add_measure_synonyms()
        test_build_retrieval_query()
        test_calculate_confidence_score()
        test_get_fallback_candidates()
        test_process_chroma_results()

        # Test main retrieve_node function
        test_retrieve_node_success()
        test_retrieve_node_fallback()
        test_retrieve_node_error_cases()

        print("=" * 60)
        print("🎉 ALL TESTS PASSED! retrieve_node is working correctly!")
        print("✅ Ready for GitHub Actions CI/CD")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("🚫 GitHub Actions will fail this build")
        raise
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        print("🚫 GitHub Actions will fail this build")
        raise


if __name__ == "__main__":
    main()
