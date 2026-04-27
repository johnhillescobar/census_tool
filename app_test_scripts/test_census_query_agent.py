"""Strict-contract tests for CensusQueryAgent parsing."""

import json

import pytest

from src.agents.census_query_agent import CensusQueryAgent


def _strict_census_data(
    *,
    headers: list[str],
    rows: list[list[str]],
    year: int = 2023,
    dataset: str = "acs/acs5",
    variables: list[str] | None = None,
    geo_for: dict[str, str] | None = None,
    geo_in: dict[str, str] | None = None,
) -> dict:
    if variables is None:
        variables = headers
    if geo_for is None:
        geo_for = {"place": "51000"}
    if geo_in is None:
        geo_in = {"state": "36"}

    return {
        "success": True,
        "request": {
            "year": year,
            "dataset": dataset,
            "variables": variables,
            "geo_for": geo_for,
            "geo_in": geo_in,
            "geo_in_chained": [],
        },
        "headers": headers,
        "records": [
            {"values": {header: str(row[i]) for i, header in enumerate(headers)}}
            for row in rows
        ],
        "row_count": len(rows),
        "error": None,
        "error_message": None,
    }


class TestAgentParsing:
    """Test suite for strict agent output parsing methods."""

    def test_parse_direct_json_strict_contract(self):
        output = json.dumps(
            {
                "census_data": _strict_census_data(
                    headers=["NAME"],
                    rows=[["California"]],
                    variables=["NAME"],
                ),
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

        assert parsed.census_data is not None
        assert parsed.census_data.success is True
        assert parsed.census_data.headers == ["NAME"]
        assert parsed.census_data.records[0].values["NAME"] == "California"
        assert parsed.answer_text == "test answer"
        assert len(parsed.footnotes) == 1

    def test_parse_with_final_answer_prefix_strict_contract(self):
        json_data = {
            "census_data": _strict_census_data(
                headers=["NAME", "B01003_001E"],
                rows=[["California", "39538223"]],
                variables=["NAME", "B01003_001E"],
            ),
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

        assert parsed.census_data is not None
        assert parsed.census_data.success is True
        assert parsed.census_data.headers == ["NAME", "B01003_001E"]
        assert parsed.census_data.records[0].values["NAME"] == "California"
        assert "California" in parsed.answer_text
        assert parsed.charts_needed[0].type == "bar"

    def test_parse_large_strict_structure(self):
        headers = ["NAME"] + [f"CP03_{i:03d}E" for i in range(100)]
        rows = [
            [f"County {i}"] + [str(j * i) for j in range(100)] for i in range(67)
        ]
        large_json = {
            "census_data": _strict_census_data(
                headers=headers,
                rows=rows,
                variables=headers,
                geo_for={"county": "*"},
                geo_in={"state": "12"},
            ),
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

        assert parsed.census_data is not None
        assert parsed.census_data.row_count == 67
        assert len(parsed.census_data.headers) == 101
        assert parsed.census_data.records[0].values["NAME"] == "County 0"
        assert parsed.tables_needed[0].format == "csv"

    def test_parse_with_escaped_quotes_in_strict_records(self):
        json_data = {
            "census_data": _strict_census_data(
                headers=['County "Name"', "Value"],
                rows=[['Miami-Dade "Metro"', "2500"]],
                variables=['County "Name"', "Value"],
            ),
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

        assert parsed.census_data is not None
        assert parsed.census_data.headers[0] == 'County "Name"'
        assert parsed.census_data.records[0].values['County "Name"'] == 'Miami-Dade "Metro"'
        assert '"quotes"' in parsed.answer_text

    def test_parse_solution_rejects_invalid_strict_structure(self):
        output = json.dumps(
            {
                "census_data": {"success": True},
                "data_summary": "invalid payload",
                "reasoning_trace": "invalid payload",
                "answer_text": "invalid payload",
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [],
            }
        )
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert parsed.census_data is None
        assert parsed.answer_text == "Agent execution completed but output parsing failed"

    def test_parse_multiline_output_with_thoughts_strict_contract(self):
        json_data = {
            "census_data": _strict_census_data(
                headers=["NAME"],
                rows=[["Test County"]],
                variables=["NAME"],
            ),
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
Action: strict_census_api_call
Action Input: {{"year": 2023, "dataset": "acs/acs5"}}
Observation: Got data
Thought: I now know the final answer
Final Answer: {json.dumps(json_data)}"""
        result = {"output": output}
        agent = CensusQueryAgent()
        parsed = agent._parse_solution(result)

        assert parsed.census_data is not None
        assert parsed.census_data.success is True
        assert parsed.answer_text == "Final answer text"

    def test_parse_handles_special_characters_in_strict_records(self):
        json_data = {
            "census_data": _strict_census_data(
                headers=["NAME", "POP"],
                rows=[
                    ["St. Mary's County", "100"],
                    ["O'Brien County", "200"],
                    ["Prince George's County", "300"],
                ],
                variables=["NAME", "POP"],
            ),
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

        assert parsed.census_data is not None
        assert parsed.census_data.records[0].values["NAME"] == "St. Mary's County"
        assert parsed.census_data.records[1].values["NAME"] == "O'Brien County"
        assert (
            parsed.census_data.records[2].values["NAME"] == "Prince George's County"
        )

    def test_parse_solution_accepts_strict_agent_output(self):
        output = {
            "census_data": _strict_census_data(
                headers=["NAME", "B01003_001E"],
                rows=[["New York city, New York", "8336817"]],
                variables=["NAME", "B01003_001E"],
            ),
            "data_summary": "NYC population",
            "reasoning_trace": "Used strict_census_api_call",
            "answer_text": "NYC population answer",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }

        agent = CensusQueryAgent()
        parsed = agent._try_direct_json_parse(
            json.dumps(output), {"output": json.dumps(output)}
        )

        assert parsed is not None
        assert parsed.census_data is not None
        assert parsed.census_data.success is True
        assert parsed.census_data.request is not None
        assert parsed.census_data.request.dataset == "acs/acs5"

    def test_parse_solution_rejects_legacy_census_data_table_shape(self):
        legacy_output = {
            "census_data": {
                "success": True,
                "data": [
                    ["NAME", "B01003_001E"],
                    ["New York city, New York", "8336817"],
                ],
            },
            "data_summary": "legacy payload",
            "reasoning_trace": "legacy output",
            "answer_text": "legacy answer",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }

        agent = CensusQueryAgent()
        parsed = agent._try_direct_json_parse(
            json.dumps(legacy_output),
            {"output": json.dumps(legacy_output)},
        )

        assert parsed is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
