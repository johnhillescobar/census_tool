"""
Integration tests for expanded geography support
Tests the full workflow from agent to API with tribal and statistical areas
"""

import pytest
import json
from src.tools.census_api_tool import CensusAPITool
from src.tools.geography_validation_tool import GeographyValidationTool


class FakeResponse:
    """Mock response for Census API"""

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._data


# ============================================================================
# Integration Test: Tribal Area Query
# ============================================================================


def test_tribal_area_query_integration(monkeypatch):
    """Test querying tribal area data through CensusAPITool"""
    tool = CensusAPITool()

    # Mock Census API response
    census_data = [
        [
            "NAME",
            "B01003_001E",
            "american indian area/alaska native area (reservation or statistical entity only)",
        ],
        ["Navajo Nation Reservation", "173667", "5620R"],
    ]

    def fake_fetch(dataset, year, variables, geo):
        return {
            "success": True,
            "data": census_data,
            "url": "https://api.census.gov/...",
        }

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return (
            "american indian area/alaska native area (reservation or statistical entity only)",
            "5620R",
            [],
        )

    def fake_build_filters(**kwargs):
        return {
            "for": "american%20indian%20area/alaska%20native%20area%20(reservation%20or%20statistical%20entity%20only):5620R"
        }

    monkeypatch.setattr("src.tools.census_api_tool.fetch_census_data", fake_fetch)
    monkeypatch.setattr(
        "src.tools.census_api_tool.build_geo_filters", fake_build_filters
    )
    monkeypatch.setattr(
        "src.utils.census_api_utils.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr("src.tools.census_api_tool.record_event", lambda *args: None)

    input_json = json.dumps(
        {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME", "B01003_001E"],
            "geo_for": {
                "american indian area/alaska native area (reservation or statistical entity only)": "5620R"
            },
            "geo_in": {},
        }
    )

    result = tool._run(input_json)
    result_dict = json.loads(result)

    assert result_dict["success"] is True
    assert len(result_dict["data"]["data"]) == 2
    assert "Navajo Nation Reservation" in str(result_dict["data"])


# ============================================================================
# Integration Test: Metro Area Query
# ============================================================================


def test_metro_area_query_integration(monkeypatch):
    """Test querying metro area data through CensusAPITool"""
    tool = CensusAPITool()

    census_data = [
        [
            "NAME",
            "B01003_001E",
            "metropolitan statistical area/micropolitan statistical area",
        ],
        ["New York-Newark-Jersey City, NY-NJ-PA Metro Area", "19768458", "35620"],
    ]

    def fake_fetch(dataset, year, variables, geo):
        return {
            "success": True,
            "data": census_data,
            "url": "https://api.census.gov/...",
        }

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return (
            "metropolitan statistical area/micropolitan statistical area",
            "35620",
            [],
        )

    def fake_build_filters(**kwargs):
        return {
            "for": "metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620"
        }

    monkeypatch.setattr("src.tools.census_api_tool.fetch_census_data", fake_fetch)
    monkeypatch.setattr(
        "src.tools.census_api_tool.build_geo_filters", fake_build_filters
    )
    monkeypatch.setattr(
        "src.utils.census_api_utils.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr("src.tools.census_api_tool.record_event", lambda *args: None)

    input_json = json.dumps(
        {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME", "B01003_001E"],
            "geo_for": {
                "metropolitan statistical area/micropolitan statistical area": "35620"
            },
            "geo_in": {},
        }
    )

    result = tool._run(input_json)
    result_dict = json.loads(result)

    assert result_dict["success"] is True
    assert "New York" in str(result_dict["data"])


# ============================================================================
# Integration Test: Auto-Repair Bad Ordering
# ============================================================================


def test_auto_repair_bad_ordering_integration(monkeypatch):
    """Test that bad geography ordering is automatically repaired"""
    tool = CensusAPITool()

    census_data = [
        ["NAME", "B01003_001E", "county", "state"],
        ["Los Angeles County, California", "9829544", "037", "06"],
    ]

    def fake_fetch(dataset, year, variables, geo):
        return {
            "success": True,
            "data": census_data,
            "url": "https://api.census.gov/...",
        }

    # Simulate reordering: county provided in geo_for with state, should be moved to geo_in
    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        # Correctly extracts county as target and state as parent
        return ("county", "*", [("state", "06")])

    def fake_build_filters(**kwargs):
        return {"for": "county:*", "in": "state:06"}

    monkeypatch.setattr("src.tools.census_api_tool.fetch_census_data", fake_fetch)
    monkeypatch.setattr(
        "src.tools.census_api_tool.build_geo_filters", fake_build_filters
    )
    monkeypatch.setattr(
        "src.utils.census_api_utils.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr("src.tools.census_api_tool.record_event", lambda *args: None)

    # Provide bad ordering: multiple items in geo_for
    input_json = json.dumps(
        {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME", "B01003_001E"],
            "geo_for": {"county": "*", "state": "06"},  # Bad: both in geo_for
            "geo_in": {},
        }
    )

    result = tool._run(input_json)
    result_dict = json.loads(result)

    # Should succeed despite bad input because of auto-repair
    assert result_dict["success"] is True


# ============================================================================
# Integration Test: Missing Parent Detection
# ============================================================================


def test_missing_parent_detection_integration(monkeypatch):
    """Test that missing parent geography is detected and reported"""
    validation_tool = GeographyValidationTool()

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return ("county", "*", [])  # No parents provided

    def fake_validate_hierarchy(dataset, year, for_token, provided_parents):
        return (
            False,
            ["state"],
            "Missing required parent geography: state. For 'county', you must specify: ['state']",
        )

    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_geography_hierarchy",
        fake_validate_hierarchy,
    )

    input_json = json.dumps(
        {
            "dataset": "acs/acs5",
            "year": 2023,
            "geo_for": {"county": "*"},
            "geo_in": {},  # Missing state
        }
    )

    result = validation_tool._run(input_json)
    result_dict = json.loads(result)

    assert result_dict["is_valid"] is False
    assert len(result_dict["errors"]) > 0
    assert "state" in result_dict["errors"][0]


# ============================================================================
# Integration Test: (or part) Geography
# ============================================================================


def test_part_geography_query_integration(monkeypatch):
    """Test querying (or part) geographies under parent statistical areas"""
    tool = CensusAPITool()

    census_data = [
        [
            "NAME",
            "B01003_001E",
            "county (or part)",
            "metropolitan statistical area/micropolitan statistical area",
        ],
        ["Bronx County, NY", "1472654", "005", "35620"],
        ["Kings County, NY", "2736074", "047", "35620"],
    ]

    def fake_fetch(dataset, year, variables, geo):
        return {
            "success": True,
            "data": census_data,
            "url": "https://api.census.gov/...",
        }

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return (
            "county (or part)",
            "*",
            [("metropolitan statistical area/micropolitan statistical area", "35620")],
        )

    def fake_build_filters(**kwargs):
        return {
            "for": "county%20(or%20part):*",
            "in": "metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620",
        }

    monkeypatch.setattr("src.tools.census_api_tool.fetch_census_data", fake_fetch)
    monkeypatch.setattr(
        "src.tools.census_api_tool.build_geo_filters", fake_build_filters
    )
    monkeypatch.setattr(
        "src.utils.census_api_utils.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr("src.tools.census_api_tool.record_event", lambda *args: None)

    input_json = json.dumps(
        {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME", "B01003_001E"],
            "geo_for": {"county (or part)": "*"},
            "geo_in": {
                "metropolitan statistical area/micropolitan statistical area": "35620"
            },
        }
    )

    result = tool._run(input_json)
    result_dict = json.loads(result)

    assert result_dict["success"] is True
    assert "Bronx County" in str(result_dict["data"]) or "Kings County" in str(
        result_dict["data"]
    )


# ============================================================================
# Integration Test: Validation Before API Call
# ============================================================================


def test_validation_before_api_call_workflow(monkeypatch):
    """Test the recommended workflow: validate first, then call API"""
    validation_tool = GeographyValidationTool()
    api_tool = CensusAPITool()

    # Step 1: Validate parameters
    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return ("county", "*", [("state", "06")])

    def fake_validate_hierarchy(dataset, year, for_token, provided_parents):
        return (True, [], "")

    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_geography_hierarchy",
        fake_validate_hierarchy,
    )

    validation_input = json.dumps(
        {
            "dataset": "acs/acs5",
            "year": 2023,
            "geo_for": {"county": "*"},
            "geo_in": {"state": "06"},
        }
    )

    validation_result = validation_tool._run(validation_input)
    validation_dict = json.loads(validation_result)

    assert validation_dict["is_valid"] is True

    # Step 2: Use validated parameters in API call
    census_data = [
        ["NAME", "B01003_001E", "county", "state"],
        ["Los Angeles County, California", "9829544", "037", "06"],
    ]

    def fake_fetch(dataset, year, variables, geo):
        return {
            "success": True,
            "data": census_data,
            "url": "https://api.census.gov/...",
        }

    def fake_build_filters(**kwargs):
        return {"for": "county:*", "in": "state:06"}

    monkeypatch.setattr("src.tools.census_api_tool.fetch_census_data", fake_fetch)
    monkeypatch.setattr(
        "src.tools.census_api_tool.build_geo_filters", fake_build_filters
    )
    monkeypatch.setattr(
        "src.utils.census_api_utils.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr("src.tools.census_api_tool.record_event", lambda *args: None)

    api_input = json.dumps(
        {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["NAME", "B01003_001E"],
            "geo_for": validation_dict["repaired_for"],
            "geo_in": validation_dict["repaired_in"],
        }
    )

    api_result = api_tool._run(api_input)
    api_dict = json.loads(api_result)

    assert api_dict["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
