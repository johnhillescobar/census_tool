import json

from src.tools.variable_validation_tool import VariableValidationTool


def test_variable_validation_tool_validate(monkeypatch):
    tool = VariableValidationTool()

    def fake_validate(dataset, year, variables):
        return {"valid": variables, "invalid": [], "warnings": []}

    monkeypatch.setattr(
        "src.tools.variable_validation_tool.validate_variables", fake_validate
    )

    payload = {
        "dataset": "acs/acs5",
        "year": 2023,
        "variables": ["B01003_001E"],
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["valid"] == ["B01003_001E"]


def test_variable_validation_tool_list(monkeypatch):
    tool = VariableValidationTool()

    def fake_list(dataset, year, table_code=None, concept=None, limit=20):
        return {"dataset": dataset, "year": year, "variables": [{"var": "B01003_001E"}]}

    monkeypatch.setattr("src.tools.variable_validation_tool.list_variables", fake_list)

    payload = {
        "action": "list_variables",
        "dataset": "acs/acs5",
        "year": 2023,
        "table_code": "B01003",
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["variables"][0]["var"] == "B01003_001E"
