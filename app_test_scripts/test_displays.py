"""
Test script for display functions - testing the fixes you made
"""

import sys
import os
from io import StringIO
from unittest.mock import patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.displays import (
    display_results,
    display_single_value,
    display_series,
    display_table,
    display_not_census,
)


def test_display_single_value():
    """Test the display_single_value function you fixed"""
    print("Testing display_single_value...")

    # Test data for single value display
    final = {
        "type": "single",
        "value": "8,804,190",
        "geo": "New York City",
        "year": "2023",
        "variable": "B01003_001E",
        "dataset": "ACS 5-Year Estimates",
    }

    # Capture output
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_single_value(final)
        output = fake_out.getvalue()

    # Assertions
    assert "New York City" in output, "Should display location"
    assert "2023" in output, "Should display year"
    assert "8,804,190" in output, "Should display value"
    assert "B01003_001E" in output, "Should display variable"

    print("✅ display_single_value test passed!")


def test_display_series():
    """Test the display_series function"""
    print("Testing display_series...")

    # Test data for series display
    final = {
        "type": "series",
        "data": [
            {"year": "2020", "value": 8336817, "formatted_value": "8,336,817"},
            {"year": "2021", "value": 8336817, "formatted_value": "8,336,817"},
            {"year": "2022", "value": 8336817, "formatted_value": "8,336,817"},
            {"year": "2023", "value": 8804190, "formatted_value": "8,804,190"},
        ],
        "geo": "New York City",
        "variable": "B01003_001E",
        "file_path": "/data/population_series.csv",
    }

    # Capture output
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_series(final)
        output = fake_out.getvalue()

    # Assertions
    assert "New York City" in output, "Should display location"
    assert "B01003_001E" in output, "Should display variable"
    assert "2020: 8,336,817" in output, "Should display time series data"
    assert "2023: 8,804,190" in output, "Should display latest data"
    assert "Full data saved to:" in output, "Should show file path"

    print("✅ display_series test passed!")


def test_display_table():
    """Test the display_table function"""
    print("Testing display_table...")

    # Test data for table display
    final = {
        "type": "table",
        "data": [
            {"NAME": "Bronx County", "B01003_001E": 1472654},
            {"NAME": "Kings County", "B01003_001E": 2736074},
            {"NAME": "New York County", "B01003_001E": 1694251},
            {"NAME": "Queens County", "B01003_001E": 2405464},
            {"NAME": "Richmond County", "B01003_001E": 495747},
        ],
        "total_rows": 5,
        "columns": ["NAME", "B01003_001E"],
        "file_path": "/data/nyc_counties.csv",
    }

    # Capture output
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_table(final)
        output = fake_out.getvalue()

    # Assertions
    assert "5 rows" in output, "Should display row count"
    assert "NAME | B01003_001E" in output, "Should display column headers"
    assert "Bronx County" in output, "Should display table data"
    assert "Full data saved to:" in output, "Should show file path"

    print("✅ display_table test passed!")


def test_display_not_census():
    """Test the display_not_census function"""
    print("Testing display_not_census...")

    # Test data for non-census display
    final = {
        "type": "not_census",
        "message": "I can only help with Census data questions.",
        "suggestion": "Try asking about population, income, or demographics.",
    }

    # Capture output
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_not_census(final)
        output = fake_out.getvalue()

    # Assertions
    assert "I can only help with Census data questions." in output, (
        "Should display message"
    )
    assert "Try asking about population" in output, "Should display suggestion"

    print("✅ display_not_census test passed!")


def test_display_results():
    """Test the main display_results function you fixed"""
    print("Testing display_results...")

    # Test successful single value result
    result = {
        "final": {
            "type": "single",
            "value": "8,804,190",
            "geo": "New York City",
            "year": "2023",
            "variable": "B01003_001E",
            "footnotes": ["Data from ACS 5-Year Estimates, 2023"],
        },
        "logs": ["data: processed 1 queries successfully"],
    }

    # Capture output
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_results(result)
        output = fake_out.getvalue()

    # Assertions
    assert "CENSUS DATA RESULTS" in output, "Should display header"
    assert "Answer Type: single" in output, "Should display answer type"
    assert "New York City" in output, "Should display location"
    assert "8,804,190" in output, "Should display value"
    assert "Footnotes:" in output, "Should display footnotes"
    assert "System Logs:" in output, "Should display logs"

    print("✅ display_results test passed!")


def test_display_results_with_error():
    """Test display_results with error"""
    print("Testing display_results with error...")

    # Test error result
    result = {"error": "No data found for the specified criteria", "final": None}

    # Capture output
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_results(result)
        output = fake_out.getvalue()

    # Assertions - check for actual error message format
    assert "[ERROR] Error:" in output, "Should display error message"
    assert "No data found" in output, "Should contain error details"

    print("✅ display_results error test passed!")


def run_all_tests():
    """Run all display function tests"""
    print("=== RUNNING DISPLAY FUNCTION TESTS ===\n")

    try:
        test_display_single_value()
        test_display_series()
        test_display_table()
        test_display_not_census()
        test_display_results()
        test_display_results_with_error()

        print("\n🎉 ALL DISPLAY FUNCTION TESTS PASSED! 🎉")
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
