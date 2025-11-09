import json

from src.tools.area_resolution_tool import AreaResolutionTool


def test_area_resolution_tool_returns_components(monkeypatch):
    tool = AreaResolutionTool()

    composite_result = {
        "code": "061",
        "geo_id": "0500000US36061",
        "full_name": "New York County, New York",
        "components": [
            {"code": "005", "full_name": "Bronx County, New York"},
            {"code": "047", "full_name": "Kings County, New York"},
        ],
        "match_type": "Composite",
        "confidence": 1.0,
    }

    monkeypatch.setattr(
        "src.tools.area_resolution_tool.GeographyRegistry",
        lambda: type(
            "StubRegistry",
            (object,),
            {"find_area_code": lambda self, **kwargs: composite_result},
        )(),
    )

    payload = {
        "name": "New York City",
        "geography_type": "place",
        "dataset": "acs/acs5",
        "year": 2023,
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["match_type"] == "Composite"
    assert len(data["components"]) == 2

