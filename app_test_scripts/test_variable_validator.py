from src.utils import variable_validator


class FakeCollection:
    def __init__(self, metadatas):
        self._metadatas = metadatas

    def get(self, **kwargs):
        return {"metadatas": self._metadatas}


class FakeClient:
    def __init__(self, metadatas):
        self._collection = FakeCollection(metadatas)

    def get_collection(self, name):
        return self._collection


def test_validate_variables_uses_chroma(monkeypatch):
    metadatas = [
        {
            "var": "B01003_001E",
            "dataset": "acs/acs5",
            "years_available": "2018,2019,2020,2021,2022,2023",
            "concept": "TOTAL POPULATION",
            "label": "Total population",
            "universe": "Population",
        }
    ]
    monkeypatch.setattr(
        variable_validator, "initialize_chroma_client", lambda: FakeClient(metadatas)
    )
    monkeypatch.setattr(
        variable_validator, "_fetch_variables_json", lambda dataset, year: {}
    )

    result = variable_validator.validate_variables(
        dataset="acs/acs5", year=2023, variables=["B01003_001E"]
    )
    assert result["valid"] == ["B01003_001E"]
    assert result["invalid"] == []
    assert result["source"]["B01003_001E"] == "chroma"


def test_validate_variables_live_fallback(monkeypatch):
    monkeypatch.setattr(
        variable_validator, "initialize_chroma_client", lambda: FakeClient([])
    )

    live_catalog = {
        "B01003_001E": {
            "concept": "TOTAL POPULATION",
            "label": "Total population",
            "universe": "Population",
        }
    }
    monkeypatch.setattr(
        variable_validator, "_fetch_variables_json", lambda dataset, year: live_catalog
    )

    result = variable_validator.validate_variables(
        dataset="acs/acs5", year=2023, variables=["B01003_001E"]
    )
    assert result["valid"] == ["B01003_001E"]
    assert result["source"]["B01003_001E"] == "live"
    assert "B01003_001E" not in result["invalid"]


def test_validate_variables_provides_alternatives(monkeypatch):
    monkeypatch.setattr(
        variable_validator, "initialize_chroma_client", lambda: FakeClient([])
    )

    live_catalog = {
        "B01003_001E": {"concept": "TOTAL POPULATION", "label": "Total population"},
        "B01003_002E": {
            "concept": "TOTAL POPULATION",
            "label": "Total population (male)",
        },
        "B19013_001E": {"concept": "MEDIAN HOUSEHOLD INCOME", "label": "Median income"},
    }
    monkeypatch.setattr(
        variable_validator, "_fetch_variables_json", lambda dataset, year: live_catalog
    )

    result = variable_validator.validate_variables(
        dataset="acs/acs5", year=2023, variables=["B01001_009E"]
    )
    assert result["invalid"] == ["B01001_009E"]
    assert result["alternatives"]["B01001_009E"]


def test_list_variables_filters(monkeypatch):
    live_catalog = {
        "B01003_001E": {"concept": "TOTAL POPULATION", "label": "Total population"},
        "B01003_002E": {
            "concept": "TOTAL POPULATION",
            "label": "Total population (male)",
        },
        "S0101_C01_001E": {
            "concept": "AGE BY SEX",
            "label": "Total population",
        },
    }
    monkeypatch.setattr(
        variable_validator, "_fetch_variables_json", lambda dataset, year: live_catalog
    )

    response = variable_validator.list_variables(
        dataset="acs/acs5", year=2023, table_code="B01003"
    )
    assert response["count"] == 2
    names = [item["var"] for item in response["variables"]]
    assert "B01003_001E" in names and "B01003_002E" in names
