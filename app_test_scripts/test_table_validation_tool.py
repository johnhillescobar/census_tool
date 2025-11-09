import json

from src.tools.table_validation_tool import TableValidationTool


def test_table_validation_tool_supported(monkeypatch):
    tool = TableValidationTool()

    def fake_supported(dataset, year, geography_level):
        return {
            "dataset": dataset,
            "year": year,
            "geography_level": geography_level,
            "normalized_level": geography_level.lower(),
            "supported": True,
            "available_levels": ["state", "county"],
        }

    monkeypatch.setattr(
        "src.tools.table_validation_tool.geography_supported", fake_supported
    )

    payload = {
        "table_code": "B01003",
        "geography_level": "county",
        "dataset": "acs/acs5",
        "year": 2023,
    }
    data = json.loads(tool._run(json.dumps(payload)))
    assert data["supported"] is True
    assert data["table_code"] == "B01003"


def test_table_validation_tool_invalid_input():
    tool = TableValidationTool()
    result = tool._run(json.dumps({"table_code": "B01003"}))
    assert result.startswith("Error:")

