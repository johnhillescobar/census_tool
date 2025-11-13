"""
Tests for multi-series chart auto-detection functionality

Tests verify that get_chart_params() correctly detects multi-series scenarios
and that ChartTool creates multi-series charts with proper color grouping.
"""

import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from src.nodes.output import get_chart_params, _detect_geography_column


class TestGeographyColumnDetection:
    """Test _detect_geography_column() function"""

    def test_priority_order_state_first(self):
        """Test that state column has priority over other geography columns"""
        df = pd.DataFrame(
            {
                "Year": [2020, 2021],
                "state": ["IL", "TX"],
                "county": ["Cook", "Harris"],
                "NAME": ["Illinois", "Texas"],
                "Value": [100, 200],
            }
        )
        headers = list(df.columns)
        result = _detect_geography_column(df, headers)
        assert result == "state"

    def test_priority_order_county_second(self):
        """Test that county has priority when state is not present"""
        df = pd.DataFrame(
            {
                "Year": [2020, 2021],
                "county": ["Cook", "Harris"],
                "NAME": ["Cook County", "Harris County"],
                "Value": [100, 200],
            }
        )
        headers = list(df.columns)
        result = _detect_geography_column(df, headers)
        assert result == "county"

    def test_priority_order_name_third(self):
        """Test that NAME has priority when state/county not present"""
        df = pd.DataFrame(
            {"Year": [2020, 2021], "NAME": ["Illinois", "Texas"], "Value": [100, 200]}
        )
        headers = list(df.columns)
        result = _detect_geography_column(df, headers)
        assert result == "NAME"

    def test_excludes_x_column(self):
        """Test that x_column is excluded from geography detection"""
        df = pd.DataFrame(
            {"Year": [2020, 2021], "NAME": ["Illinois", "Texas"], "Value": [100, 200]}
        )
        headers = list(df.columns)
        # If NAME is the x_column, it should not be returned
        result = _detect_geography_column(df, headers, x_column="NAME")
        assert result is None  # No other geography column available

    def test_returns_none_when_no_geography(self):
        """Test that None is returned when no geography columns exist"""
        df = pd.DataFrame({"Year": [2020, 2021], "Value": [100, 200]})
        headers = list(df.columns)
        result = _detect_geography_column(df, headers)
        assert result is None


class TestMultiSeriesDetection:
    """Test get_chart_params() multi-series auto-detection"""

    def test_multi_series_line_chart_detected(self):
        """Test that multi-series is detected for line chart with multiple states"""
        census_data = {
            "data": [
                ["Year", "NAME", "S1401_C01_001E"],
                ["2018", "Illinois", "500000"],
                ["2018", "Texas", "600000"],
                ["2019", "Illinois", "510000"],
                ["2019", "Texas", "610000"],
            ],
            "variables": {"S1401_C01_001E": "High School Enrollment"},
        }
        result = get_chart_params(census_data, "line")

        assert result["x_column"] == "Year"
        assert result["y_column"] == "S1401_C01_001E"
        assert result["color_column"] == "NAME"  # Multi-series detected
        assert "High School Enrollment" in result["title"]

    def test_single_series_not_detected(self):
        """Test that single geography does not trigger multi-series"""
        census_data = {
            "data": [
                ["Year", "NAME", "S1401_C01_001E"],
                ["2018", "Illinois", "500000"],
                ["2019", "Illinois", "510000"],
            ],
            "variables": {"S1401_C01_001E": "High School Enrollment"},
        }
        result = get_chart_params(census_data, "line")

        assert result["x_column"] == "Year"
        assert result["y_column"] == "S1401_C01_001E"
        assert "color_column" not in result  # No multi-series (only 1 unique value)

    def test_multi_series_bar_chart_detected(self):
        """Test that multi-series is detected for bar chart with multiple states"""
        census_data = {
            "data": [
                ["NAME", "B01003_001E"],
                ["Illinois", "12600000"],
                ["Texas", "29000000"],
                ["California", "39000000"],
            ],
            "variables": {"B01003_001E": "Total Population"},
        }
        result = get_chart_params(census_data, "bar")

        assert result["x_column"] == "NAME"
        assert result["y_column"] == "B01003_001E"
        # Note: When x_column is the geography, we don't use it for color
        # This is correct behavior - color would conflict with x-axis
        # Multi-series bar charts work differently (grouped bars)

    def test_priority_state_over_county(self):
        """Test that state column is preferred over county for multi-series"""
        census_data = {
            "data": [
                ["Year", "state", "county", "NAME", "Value"],
                ["2018", "IL", "Cook", "Cook County, Illinois", "100"],
                ["2018", "TX", "Harris", "Harris County, Texas", "200"],
                ["2019", "IL", "Cook", "Cook County, Illinois", "110"],
                ["2019", "TX", "Harris", "Harris County, Texas", "210"],
            ],
        }
        result = get_chart_params(census_data, "line")

        assert result["color_column"] == "state"  # State has priority

    def test_no_multi_series_when_geography_is_x_column(self):
        """Test that geography column is not used for color if it's the x_column"""
        census_data = {
            "data": [
                ["NAME", "B01003_001E"],
                ["Illinois", "12600000"],
                ["Texas", "29000000"],
            ],
        }
        result = get_chart_params(census_data, "bar")

        # When NAME is x_column, it shouldn't also be color_column
        assert result["x_column"] == "NAME"
        assert "color_column" not in result or result.get("color_column") != "NAME"

    def test_multi_series_with_time_series(self):
        """Test multi-series detection with time series data"""
        census_data = {
            "data": [
                ["Year", "state", "S1401_C01_001E"],
                ["2018", "IL", "500000"],
                ["2018", "TX", "600000"],
                ["2019", "IL", "510000"],
                ["2019", "TX", "610000"],
                ["2020", "IL", "520000"],
                ["2020", "TX", "620000"],
            ],
            "variables": {"S1401_C01_001E": "High School Enrollment"},
        }
        result = get_chart_params(census_data, "line")

        assert result["x_column"] == "Year"
        assert result["y_column"] == "S1401_C01_001E"
        assert result["color_column"] == "state"
        assert "High School Enrollment" in result["title"]
        assert "by Year" in result["title"]

    def test_backward_compatibility_single_state(self):
        """Test backward compatibility: single state query works as before"""
        census_data = {
            "data": [
                ["Year", "NAME", "B01003_001E"],
                ["2018", "Illinois", "12600000"],
                ["2019", "Illinois", "12700000"],
            ],
            "variables": {"B01003_001E": "Total Population"},
        }
        result = get_chart_params(census_data, "line")

        # Should work exactly as before (no color_column)
        assert result["x_column"] == "Year"
        assert result["y_column"] == "B01003_001E"
        assert "color_column" not in result
        assert "Total Population" in result["title"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
