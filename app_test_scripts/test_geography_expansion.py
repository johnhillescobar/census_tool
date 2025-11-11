"""
Tests for expanded geography support (tribal areas, statistical areas, validation)
"""

import pytest
import json
from src.utils.geography_registry import GeographyRegistry
from src.utils.chroma_utils import (
    validate_geography_hierarchy,
    validate_and_fix_geo_params,
)
from src.tools.geography_validation_tool import GeographyValidationTool


class FakeResponse:
    """Mock response for requests.get"""

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._data


# ============================================================================
# Phase 1: Tribal Geography Tests
# ============================================================================


def test_enumerate_tribal_areas_with_suffix(monkeypatch, tmp_path):
    """Test that tribal area codes with R/T suffixes are properly detected"""
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    # Mock API response with tribal areas
    tribal_data = [
        [
            "NAME",
            "GEO_ID",
            "american indian area/alaska native area (reservation or statistical entity only)",
        ],
        ["Navajo Nation Reservation", "2500000US5620R", "5620R"],
        ["Agua Caliente Reservation", "2500000US0010R", "0010R"],
    ]

    def fake_get(url, timeout):
        return FakeResponse(tribal_data)

    monkeypatch.setattr("requests.get", fake_get)

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return (
            "american indian area/alaska native area (reservation or statistical entity only)",
            "*",
            [],
        )

    monkeypatch.setattr(
        "src.utils.geography_registry.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr(
        "src.utils.geography_registry.build_geo_filters",
        lambda **kwargs: {"for": "test"},
    )
    monkeypatch.setattr("src.utils.geography_registry.record_event", lambda *args: None)

    # Enumerate tribal areas
    areas = registry.enumerate_tribal_areas(
        "acs/acs5",
        2023,
        "american indian area/alaska native area (reservation or statistical entity only)",
    )

    assert len(areas) == 2
    assert "Navajo Nation Reservation" in areas
    assert areas["Navajo Nation Reservation"]["code"] == "5620R"
    assert areas["Navajo Nation Reservation"]["code_base"] == "5620"
    assert areas["Navajo Nation Reservation"]["suffix"] == "R"


def test_resolve_tribal_area_fuzzy_match(monkeypatch, tmp_path):
    """Test fuzzy matching for tribal area names"""
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    # Mock enumeration
    def fake_enumerate(dataset, year, geo_token, state_code, force_refresh=False):
        return {
            "Navajo Nation Reservation and Off-Reservation Trust Land": {
                "code": "5620R",
                "code_base": "5620",
                "suffix": "R",
                "geo_id": "2500000US5620R",
                "full_name": "Navajo Nation Reservation and Off-Reservation Trust Land",
            }
        }

    registry.enumerate_tribal_areas = fake_enumerate
    monkeypatch.setattr("src.utils.geography_registry.record_event", lambda *args: None)

    # Test fuzzy match
    result = registry.resolve_tribal_area("Navajo", "acs/acs5", 2023)

    assert result is not None
    assert result["code"] == "5620R"
    assert result["suffix"] == "R"
    assert result["confidence"] > 0.7


def test_find_area_code_routes_to_tribal(monkeypatch, tmp_path):
    """Test that find_area_code properly routes tribal geography requests"""
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    # Mock resolve_tribal_area
    def fake_resolve(name, dataset, year, geo_token, state_code):
        return {
            "code": "5620R",
            "confidence": 0.95,
            "full_name": "Navajo Nation Reservation",
        }

    registry.resolve_tribal_area = fake_resolve

    result = registry.find_area_code(
        "Navajo",
        "american indian area/alaska native area (reservation or statistical entity only)",
        "acs/acs5",
        2023,
    )

    assert result is not None
    assert result["code"] == "5620R"


# ============================================================================
# Phase 2: Statistical Area Tests
# ============================================================================


def test_enumerate_statistical_areas(monkeypatch, tmp_path):
    """Test enumeration of metropolitan statistical areas"""
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    metro_data = [
        [
            "NAME",
            "GEO_ID",
            "metropolitan statistical area/micropolitan statistical area",
        ],
        ["New York-Newark-Jersey City, NY-NJ-PA Metro Area", "3100000US35620", "35620"],
        ["Los Angeles-Long Beach-Anaheim, CA Metro Area", "3100000US31080", "31080"],
    ]

    def fake_get(url, timeout):
        return FakeResponse(metro_data)

    monkeypatch.setattr("requests.get", fake_get)

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return ("metropolitan statistical area/micropolitan statistical area", "*", [])

    monkeypatch.setattr(
        "src.utils.geography_registry.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr(
        "src.utils.geography_registry.build_geo_filters",
        lambda **kwargs: {"for": "test"},
    )
    monkeypatch.setattr("src.utils.geography_registry.record_event", lambda *args: None)

    areas = registry.enumerate_statistical_areas(
        "metropolitan statistical area/micropolitan statistical area", "acs/acs5", 2023
    )

    assert len(areas) == 2
    assert "New York-Newark-Jersey City, NY-NJ-PA Metro Area" in areas
    assert areas["New York-Newark-Jersey City, NY-NJ-PA Metro Area"]["code"] == "35620"


def test_resolve_statistical_area_fuzzy(monkeypatch, tmp_path):
    """Test fuzzy matching for statistical areas"""
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    def fake_enumerate(area_type, dataset, year, force_refresh=False):
        return {
            "New York-Newark-Jersey City, NY-NJ-PA Metro Area": {
                "code": "35620",
                "geo_id": "3100000US35620",
                "full_name": "New York-Newark-Jersey City, NY-NJ-PA Metro Area",
            }
        }

    registry.enumerate_statistical_areas = fake_enumerate
    monkeypatch.setattr("src.utils.geography_registry.record_event", lambda *args: None)

    result = registry.resolve_statistical_area(
        "New York metro",
        "metropolitan statistical area/micropolitan statistical area",
        "acs/acs5",
        2023,
    )

    assert result is not None
    assert result["code"] == "35620"
    assert result["confidence"] > 0.7


def test_resolve_part_geography(monkeypatch, tmp_path):
    """Test resolving (or part) geographies under parent statistical areas"""
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    county_part_data = [
        ["NAME", "GEO_ID", "county (or part)"],
        ["Bronx County, NY", "0500000US36005", "005"],
        ["Kings County, NY", "0500000US36047", "047"],
    ]

    def fake_get(url, timeout):
        return FakeResponse(county_part_data)

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(
        "src.utils.geography_registry.build_geo_filters",
        lambda **kwargs: {"for": "test", "in": "test"},
    )

    areas = registry._resolve_part_geography(
        "county (or part)",
        "metropolitan statistical area/micropolitan statistical area",
        "35620",
        "acs/acs5",
        2023,
    )

    assert len(areas) == 2
    assert "Bronx County, NY" in areas
    assert areas["Bronx County, NY"]["parent_code"] == "35620"


# ============================================================================
# Phase 3: Validation Tests
# ============================================================================


def test_validate_geography_hierarchy_valid(monkeypatch):
    """Test validation passes when all required parents are provided"""

    def fake_get_hierarchy(dataset, year, for_token):
        return ["state"]

    monkeypatch.setattr(
        "src.utils.chroma_utils.get_hierarchy_ordering", fake_get_hierarchy
    )

    is_valid, missing, error_msg = validate_geography_hierarchy(
        "acs/acs5", 2023, "county", ["state"]
    )

    assert is_valid is True
    assert len(missing) == 0
    assert error_msg == ""


def test_validate_geography_hierarchy_missing_parent(monkeypatch):
    """Test validation fails when required parent is missing"""

    def fake_get_hierarchy(dataset, year, for_token):
        return ["state"]

    def fake_initialize():
        return {"error": "test"}

    monkeypatch.setattr(
        "src.utils.chroma_utils.get_hierarchy_ordering", fake_get_hierarchy
    )
    monkeypatch.setattr(
        "src.utils.chroma_utils.initialize_chroma_client", fake_initialize
    )

    is_valid, missing, error_msg = validate_geography_hierarchy(
        "acs/acs5", 2023, "county", []
    )

    assert is_valid is False
    assert "state" in missing
    assert "Missing required parent geography" in error_msg


def test_validate_and_fix_geo_params_with_validation(monkeypatch):
    """Test validate_and_fix_geo_params with completeness validation enabled"""

    def fake_get_hierarchy(dataset, year, for_token):
        return ["state"]

    def fake_initialize():
        return {"error": "test"}

    monkeypatch.setattr(
        "src.utils.chroma_utils.get_hierarchy_ordering", fake_get_hierarchy
    )
    monkeypatch.setattr(
        "src.utils.chroma_utils.initialize_chroma_client", fake_initialize
    )

    # Should pass with state provided
    for_token, for_value, ordered_in = validate_and_fix_geo_params(
        "acs/acs5", 2023, {"county": "*"}, {"state": "06"}, validate_completeness=True
    )

    assert for_token == "county"
    assert for_value == "*"
    assert ("state", "06") in ordered_in

    # Should fail without state
    with pytest.raises(ValueError, match="Missing required parent geography"):
        validate_and_fix_geo_params(
            "acs/acs5", 2023, {"county": "*"}, {}, validate_completeness=True
        )


def test_geography_validation_tool_valid_params(monkeypatch):
    """Test GeographyValidationTool with valid parameters"""
    tool = GeographyValidationTool()

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

    input_json = json.dumps(
        {
            "dataset": "acs/acs5",
            "year": 2023,
            "geo_for": {"county": "*"},
            "geo_in": {"state": "06"},
        }
    )

    result = tool._run(input_json)
    result_dict = json.loads(result)

    assert result_dict["is_valid"] is True
    assert len(result_dict["errors"]) == 0
    assert result_dict["repaired_for"] == {"county": "*"}


def test_geography_validation_tool_missing_parent(monkeypatch):
    """Test GeographyValidationTool detects missing parent geography"""
    tool = GeographyValidationTool()

    def fake_validate(dataset, year, geo_for, geo_in, **kwargs):
        return ("county", "*", [])

    def fake_validate_hierarchy(dataset, year, for_token, provided_parents):
        return (False, ["state"], "Missing required parent geography: state")

    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_and_fix_geo_params", fake_validate
    )
    monkeypatch.setattr(
        "src.tools.geography_validation_tool.validate_geography_hierarchy",
        fake_validate_hierarchy,
    )

    input_json = json.dumps(
        {"dataset": "acs/acs5", "year": 2023, "geo_for": {"county": "*"}, "geo_in": {}}
    )

    result = tool._run(input_json)
    result_dict = json.loads(result)

    assert result_dict["is_valid"] is False
    assert len(result_dict["errors"]) > 0
    assert "Missing required parent geography" in result_dict["errors"][0]


# ============================================================================
# Phase 4: Auto-Repair Tests
# ============================================================================


def test_validate_and_fix_geo_params_reorders(monkeypatch):
    """Test that validate_and_fix_geo_params correctly reorders parent geographies"""

    def fake_get_hierarchy(dataset, year, for_token):
        # Correct order should be: state, county
        return ["state", "county"]

    monkeypatch.setattr(
        "src.utils.chroma_utils.get_hierarchy_ordering", fake_get_hierarchy
    )

    # Provide in wrong order
    for_token, for_value, ordered_in = validate_and_fix_geo_params(
        "acs/acs5",
        2023,
        {"tract": "*"},
        {"county": "037", "state": "06"},  # Wrong order
    )

    assert for_token == "tract"
    # Check that ordering is corrected
    tokens_in_order = [token for token, _ in ordered_in]
    assert tokens_in_order == ["state", "county"]


def test_token_normalization(monkeypatch):
    """Test that geography tokens are normalized correctly"""

    def fake_get_hierarchy(dataset, year, for_token):
        return []

    monkeypatch.setattr(
        "src.utils.chroma_utils.get_hierarchy_ordering", fake_get_hierarchy
    )

    # Test CBSA normalization
    for_token, for_value, ordered_in = validate_and_fix_geo_params(
        "acs/acs5", 2023, {"cbsa": "*"}, {}
    )

    assert for_token == "metropolitan statistical area/micropolitan statistical area"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
