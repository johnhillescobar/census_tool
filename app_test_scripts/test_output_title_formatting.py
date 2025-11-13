"""
Tests for chart title formatting functionality in output.py

Tests verify that format_chart_title() and get_chart_params() correctly
generate human-readable titles with variable codes when variables dict is provided.
"""

import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.nodes.output import format_chart_title, get_chart_params


class TestFormatChartTitle:
    """Test format_chart_title() function"""

    def test_with_variables_dict_bar_chart(self):
        """Test bar chart title with variables dict"""
        variables = {"B01003_001E": "Total Population"}
        result = format_chart_title("B01003_001E", "NAME", "bar", variables)
        assert result == "Total Population (B01003_001E) by NAME"

    def test_with_variables_dict_line_chart(self):
        """Test line chart title with variables dict"""
        variables = {"S2701_C01_001E": "Health Insurance Coverage"}
        result = format_chart_title("S2701_C01_001E", "NAME", "line", variables)
        assert result == "Health Insurance Coverage (S2701_C01_001E) Trend"

    def test_without_variables_dict_bar_chart(self):
        """Test bar chart title without variables dict (fallback)"""
        result = format_chart_title("B01003_001E", "NAME", "bar", None)
        assert result == "B01003_001E by NAME"

    def test_without_variables_dict_line_chart(self):
        """Test line chart title without variables dict (fallback)"""
        result = format_chart_title("S2701_C01_001E", "NAME", "line", None)
        assert result == "S2701_C01_001E Trend"

    def test_with_empty_variables_dict(self):
        """Test with empty variables dict (should fallback)"""
        result = format_chart_title("B01003_001E", "NAME", "bar", {})
        assert result == "B01003_001E by NAME"

    def test_with_empty_string_label(self):
        """Test with empty string in variables dict (should fallback)"""
        variables = {"B01003_001E": ""}
        result = format_chart_title("B01003_001E", "NAME", "bar", variables)
        assert result == "B01003_001E by NAME"

    def test_with_whitespace_only_label(self):
        """Test with whitespace-only label (should fallback)"""
        variables = {"B01003_001E": "   "}
        result = format_chart_title("B01003_001E", "NAME", "bar", variables)
        assert result == "B01003_001E by NAME"

    def test_with_unknown_chart_type(self):
        """Test with unknown chart type (should use default format)"""
        variables = {"B01003_001E": "Total Population"}
        result = format_chart_title("B01003_001E", "NAME", "unknown", variables)
        assert result == "Total Population (B01003_001E) - Census Data Visualization"

    def test_variable_not_in_dict(self):
        """Test when variable code not in variables dict"""
        variables = {"OTHER_VAR": "Other Variable"}
        result = format_chart_title("B01003_001E", "NAME", "bar", variables)
        assert result == "B01003_001E by NAME"


class TestGetChartParams:
    """Test get_chart_params() function with variables dict"""

    def test_get_chart_params_with_variables_dict(self):
        """Test get_chart_params extracts variables and formats title"""
        census_data = {
            "data": [
                ["NAME", "B01003_001E", "state"],
                ["California", "39538223", "06"],
                ["Texas", "29145505", "48"],
            ],
            "variables": {"B01003_001E": "Total Population"},
        }
        result = get_chart_params(census_data, "bar")

        assert result["x_column"] == "NAME"
        assert result["y_column"] == "B01003_001E"
        assert result["title"] == "Total Population (B01003_001E) by NAME"

    def test_get_chart_params_without_variables_dict(self):
        """Test get_chart_params without variables dict (fallback)"""
        census_data = {
            "data": [
                ["NAME", "B01003_001E", "state"],
                ["California", "39538223", "06"],
            ],
        }
        result = get_chart_params(census_data, "bar")

        assert result["x_column"] == "NAME"
        assert result["y_column"] == "B01003_001E"
        assert result["title"] == "B01003_001E by NAME"

    def test_get_chart_params_line_chart_with_variables(self):
        """Test line chart title formatting with variables"""
        census_data = {
            "data": [
                ["YEAR", "B01003_001E"],
                ["2020", "331000000"],
                ["2021", "332000000"],
            ],
            "variables": {"B01003_001E": "Total Population"},
        }
        result = get_chart_params(census_data, "line")

        assert result["x_column"] == "YEAR"
        assert result["y_column"] == "B01003_001E"
        assert result["title"] == "Total Population (B01003_001E) Trend"

    def test_get_chart_params_empty_variables_dict(self):
        """Test with empty variables dict"""
        census_data = {
            "data": [
                ["NAME", "B01003_001E"],
                ["California", "39538223"],
            ],
            "variables": {},
        }
        result = get_chart_params(census_data, "bar")

        assert result["title"] == "B01003_001E by NAME"

    def test_get_chart_params_invalid_data_format(self):
        """Test error handling for invalid data format"""
        census_data = {"data": []}  # Missing headers

        # Should raise ValueError or return fallback
        result = get_chart_params(census_data, "bar")

        # Should have fallback values
        assert "x_column" in result
        assert "y_column" in result
        assert "title" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
