from src.tools.variable_validation_tool import VariableValidationTool


def test_variable_validation_tool_validate(monkeypatch):
    tool = VariableValidationTool()

    def fake_validate(dataset, year, variables):
        return {
            "valid": variables,
            "invalid": [],
            "years_available": {var: [str(year)] for var in variables},
            "details": {
                var: {
                    "concept": "Population",
                    "label": "Population",
                    "universe": "Total population",
                    "dataset": dataset,
                }
                for var in variables
            },
            "alternatives": {},
            "source": {var: "test" for var in variables},
            "warnings": [],
        }

    monkeypatch.setattr(
        "src.tools.variable_validation_tool.validate_variables", fake_validate
    )

    payload = {
        "dataset": "acs/acs5",
        "year": 2023,
        "variables": ["B01003_001E"],
    }
    response = tool._run(payload)
    assert response.success is True
    assert response.valid == ["B01003_001E"]
    assert response.request is not None
    assert response.request.variables == ["B01003_001E"]


def test_variable_validation_tool_list(monkeypatch):
    tool = VariableValidationTool()

    def fake_list(dataset, year, table_code=None, concept=None, limit=20):
        return {
            "dataset": dataset,
            "year": year,
            "count": 1,
            "variables": [
                {
                    "var": "B01003_001E",
                    "label": "Population",
                    "concept": "Population",
                    "universe": "Total population",
                }
            ],
        }

    monkeypatch.setattr("src.tools.variable_validation_tool.list_variables", fake_list)

    payload = {
        "action": "list_variables",
        "dataset": "acs/acs5",
        "year": 2023,
        "table_code": "B01003",
    }
    response = tool._run(payload)
    assert response.success is True
    assert response.count == 1
    assert response.variables[0].var == "B01003_001E"
