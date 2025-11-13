"""
Unit tests for CensusQueryAgent parsing functionality.
Tests the robust JSON parsing methods that handle various agent output formats.
"""

import pytest
import json
from src.utils.agents.census_query_agent import CensusQueryAgent


class TestAgentParsing:
    """Test suite for agent output parsing methods."""

    def test_parse_direct_json(self):
        """Test direct JSON parsing without prefix."""
        output = json.dumps(
            {
                "census_data": {"success": True, "data": [["NAME"], ["California"]]},
                "data_summary": "test summary",
                "reasoning_trace": "test trace",
                "answer_text": "test answer",
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": ["Source: Census"],
            }
        )
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert parsed["census_data"]["success"] is True
        assert len(parsed["census_data"]["data"]) == 2
        assert parsed["census_data"]["data"][0][0] == "NAME"
        assert parsed["census_data"]["data"][1][0] == "California"
        assert parsed["answer_text"] == "test answer"
        assert len(parsed["footnotes"]) == 1

    def test_parse_with_final_answer_prefix(self):
        """Test extraction after 'Final Answer:' marker."""
        json_data = {
            "census_data": {
                "success": True,
                "data": [["NAME", "B01003_001E"], ["California", "39538223"]],
            },
            "data_summary": "Population data for California",
            "reasoning_trace": "Queried B01003 table",
            "answer_text": "California has a population of 39,538,223",
            "charts_needed": [{"type": "bar", "title": "Population"}],
            "tables_needed": [],
            "footnotes": ["Source: Census Bureau"],
        }
        output = f"Thought: I now know the final answer\nFinal Answer: {json.dumps(json_data)}"
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert parsed["census_data"]["success"] is True
        assert len(parsed["census_data"]["data"]) == 2
        assert "California" in parsed["answer_text"]
        assert parsed["charts_needed"][0]["type"] == "bar"

    def test_parse_large_nested_structure(self):
        """Test parsing with large nested arrays (67 counties × 100 variables)."""
        # Simulate large CP03 response
        headers = ["NAME"] + [f"CP03_{i:03d}E" for i in range(100)]
        data = [headers] + [
            [f"County {i}"] + [str(j * i) for j in range(100)] for i in range(67)
        ]
        large_json = {
            "census_data": {"success": True, "data": data},
            "data_summary": "Large dataset with 67 counties and 100 variables",
            "reasoning_trace": "Retrieved all CP03 data for Florida counties",
            "answer_text": "Here's the complete economic profile for 67 Florida counties",
            "charts_needed": [],
            "tables_needed": [
                {"format": "csv", "title": "Florida Counties Economic Data"}
            ],
            "footnotes": ["Source: Census Bureau, 2023 ACS 5-Year Estimates"],
        }
        output = f"Final Answer: {json.dumps(large_json)}"
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert len(parsed["census_data"]["data"]) == 68  # headers + 67 counties
        assert len(parsed["census_data"]["data"][0]) == 101  # NAME + 100 variables
        assert parsed["census_data"]["data"][1][0] == "County 0"  # Loop starts from 0
        assert parsed["tables_needed"][0]["format"] == "csv"

    def test_parse_with_escaped_quotes(self):
        """Test parsing JSON with escaped quotes in strings."""
        json_data = {
            "census_data": {
                "success": True,
                "data": [['County "Name"', "Value"], ['Miami-Dade "Metro"', "2500"]],
            },
            "data_summary": "test",
            "reasoning_trace": "test",
            "answer_text": 'County data with "quotes"',
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }
        output = f"Final Answer: {json.dumps(json_data)}"
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert 'County "Name"' in parsed["census_data"]["data"][0][0]
        assert 'Miami-Dade "Metro"' in parsed["census_data"]["data"][1][0]
        assert '"quotes"' in parsed["answer_text"]

    def test_pydantic_validation_catches_invalid_structure(self):
        """Test Pydantic validation rejects invalid structures."""
        # Missing required fields
        output = '{"census_data": {"success": true}}'  # Missing 'data' field
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        # Should fall back to empty structure
        assert parsed["census_data"] == {}
        assert (
            parsed["answer_text"]
            == "Agent execution completed but output parsing failed"
        )

    def test_parse_with_nested_objects_in_data(self):
        """Test parsing data with nested objects and null values."""
        json_data = {
            "census_data": {
                "success": True,
                "data": [
                    ["NAME", "VALUE", "MARGIN"],
                    ["California", "100", None],
                    ["Texas", "200", "null"],
                    ["Florida", "150", "5.2"],
                ],
                "variables": {
                    "B01003_001E": "Total Population",
                    "B01003_001M": "Margin of Error",
                },
            },
            "data_summary": "Population with margins",
            "reasoning_trace": "Retrieved with margins of error",
            "answer_text": "Population data includes margin of error estimates",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": ["MOE at 90% confidence"],
        }
        output = f"Thought: Retrieved data\nFinal Answer: {json.dumps(json_data)}"
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert parsed["census_data"]["success"] is True
        assert len(parsed["census_data"]["data"]) == 4
        assert parsed["census_data"]["variables"]["B01003_001E"] == "Total Population"
        assert parsed["footnotes"][0] == "MOE at 90% confidence"

    def test_parse_multiline_output_with_thoughts(self):
        """Test parsing output with multiple thought/action cycles before final answer."""
        json_data = {
            "census_data": {"success": True, "data": [["NAME"], ["Test County"]]},
            "data_summary": "Final data",
            "reasoning_trace": "Multi-step reasoning",
            "answer_text": "Final answer text",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }
        output = f"""Thought: I need to find the state code
Action: resolve_area_name
Action Input: {{"name": "Florida", "geography_type": "state"}}
Observation: {{"state": "12"}}
Thought: Now I can query the data
Action: census_api_call
Action Input: {{"year": 2023, "dataset": "acs/acs5"}}
Observation: Got data
Thought: I now know the final answer
Final Answer: {json.dumps(json_data)}"""
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert parsed["census_data"]["success"] is True
        assert parsed["answer_text"] == "Final answer text"

    def test_parse_handles_special_characters(self):
        """Test parsing with special characters in county names."""
        json_data = {
            "census_data": {
                "success": True,
                "data": [
                    ["NAME", "POP"],
                    ["St. Mary's County", "100"],
                    ["O'Brien County", "200"],
                    ["Prince George's County", "300"],
                ],
            },
            "data_summary": "Counties with apostrophes",
            "reasoning_trace": "Handled special chars",
            "answer_text": "Retrieved data for counties with special characters",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }
        output = f"Final Answer: {json.dumps(json_data)}"
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert "St. Mary's County" in parsed["census_data"]["data"][1][0]
        assert "O'Brien County" in parsed["census_data"]["data"][2][0]
        assert "Prince George's County" in parsed["census_data"]["data"][3][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
