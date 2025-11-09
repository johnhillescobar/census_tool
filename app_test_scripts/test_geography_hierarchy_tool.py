import json

from src.tools.geography_hierarchy_tool import GeographyHierarchyTool


def test_geography_hierarchy_tool_returns_order(monkeypatch):
    # Mock helper to return ordering
    monkeypatch.setattr(
        "src.tools.geography_hierarchy_tool.get_hierarchy_ordering",
        lambda dataset, year, for_level: [
            "metropolitan statistical area/micropolitan statistical area",
            "state (or part)",
        ],
    )

    # Mock initialize client -> metadata
    class DummyCollection:
        def get(self, **kwargs):
            return {
                "metadatas": [
                    {
                        "geography_hierarchy": "metropolitan statistical area/micropolitan statistical area › state (or part) › county",
                        "example_url": "for=county:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:31080%20state%20(or%20part):06",
                    }
                ]
            }

    class DummyClient:
        def get_collection(self, name):
            return DummyCollection()

    monkeypatch.setattr(
        "src.tools.geography_hierarchy_tool.initialize_chroma_client",
        lambda: DummyClient(),
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
        "src.tools.geography_hierarchy_tool.get_hierarchy_ordering",
        lambda dataset, year, for_level: [],
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
