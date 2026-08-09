import json

from src.clients.chroma_utils import HierarchyLookupResult
from src.tools.geography_hierarchy_tool import GeographyHierarchyTool


def test_geography_hierarchy_tool_returns_order(monkeypatch):
    metro_area = "metropolitan statistical area/micropolitan statistical area"
    state_part = "state (or part)"

    monkeypatch.setattr(
        "src.tools.geography_hierarchy_tool.get_hierarchy_ordering_result",
        lambda dataset, year, for_level: HierarchyLookupResult(
            status="hit",
            dataset=dataset,
            year=year,
            for_level=for_level,
            ordering=[metro_area, state_part],
            hierarchy_id="hierarchy:county",
            geography_hierarchy=f"{metro_area} › {state_part} › county",
            example_url=(
                "for=county:*&in=metropolitan%20statistical%20area/"
                "micropolitan%20statistical%20area:31080%20state%20(or%20part):06"
            ),
        ),
    )

    tool = GeographyHierarchyTool()
    payload = {
        "dataset": "acs/acs5",
        "year": 2023,
        "for_level": "county",
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["ordered_parents"] == [
        "metropolitan statistical area/micropolitan statistical area",
        "state (or part)",
    ]
    assert "warnings" in data
    assert data["geography_hierarchy"].startswith("metropolitan")


def test_geography_hierarchy_tool_handles_missing_order(monkeypatch):
    monkeypatch.setattr(
        "src.tools.geography_hierarchy_tool.get_hierarchy_ordering_result",
        lambda dataset, year, for_level: HierarchyLookupResult(
            status="empty",
            dataset=dataset,
            year=year,
            for_level=for_level,
        ),
    )

    tool = GeographyHierarchyTool()
    payload = {
        "dataset": "acs/acs5",
        "year": 2023,
        "for_level": "county",
        "parent_hint": ["state"],
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["ordered_parents"] == ["state"]
    assert data["warnings"]
