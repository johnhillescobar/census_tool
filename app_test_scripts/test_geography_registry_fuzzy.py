from src.utils.geography_registry import GeographyRegistry


def test_find_area_code_uses_fuzzy_matching(monkeypatch):
    registry = GeographyRegistry()

    sample_areas = {
        "New York County, New York": {
            "code": "061",
            "geo_id": "0500000US36061",
            "full_name": "New York County, New York",
        },
        "Albany County, New York": {
            "code": "001",
            "geo_id": "0500000US36001",
            "full_name": "Albany County, New York",
        },
    }

    monkeypatch.setattr(
        registry,
        "enumerate_areas",
        lambda dataset, year, geo_token, parent_geo: sample_areas,
    )

    result = registry.find_area_code(
        "Manhattan", "county", "acs/acs5", 2023, parent_geo={"state": "36"}
    )
    assert result is not None
    assert result["code"] == "061"
    assert result["match_type"] in {"Exact match", "Fuzzy match"}
