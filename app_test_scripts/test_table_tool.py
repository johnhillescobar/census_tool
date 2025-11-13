import json
from pathlib import Path

import pytest

pytest.importorskip("langchain_core.tools")

import pandas as pd

from src.tools.table_tool import TableTool
from src.utils.dataframe_utils import _create_dataframe_from_json


@pytest.fixture
def sample_census_payload():
    return {
        "success": True,
        "data": [
            [
                "NAME",
                "C27012_001E",
                "C27012_003E",
                "C27012_022E",
                "state",
            ],
            [
                "Alabama",
                "2,911,005",
                "1,424,082",
                "132,980",
                "01",
            ],
            [
                "Alaska",
                "421,077",
                "188,248",
                "13,041",
                "02",
            ],
        ],
    }


def test_create_dataframe_from_json_strips_formatting(sample_census_payload):
    df = _create_dataframe_from_json(sample_census_payload)

    assert df["C27012_001E"].dtype.kind in {"i", "f"}
    assert df["C27012_001E"].iloc[0] == 2911005
    assert df["C27012_003E"].iloc[1] == 188248
    # state column should remain string to preserve zero padding
    assert df["state"].dtype == object
    assert df["state"].iloc[0] == "01"


def test_run_saves_clean_csv(tmp_path, monkeypatch, sample_census_payload):
    tool = TableTool()
    monkeypatch.chdir(tmp_path)

    filename = "health_insurance_coverage_by_state_test"
    tool_input = json.dumps(
        {
            "format": "csv",
            "filename": filename,
            "title": "Test Table",
            "data": sample_census_payload,
        }
    )

    result = tool._run(tool_input)

    expected_path = Path("data/tables") / f"{filename}.csv"
    assert expected_path.exists(), f"Expected table file at {expected_path}"

    saved = pd.read_csv(expected_path)
    assert saved["C27012_022E"].iloc[0] == 132980
    assert "Table created successfully" in result


def test_preserves_identifier_columns():
    """Test that Area Name, GeoID, CSA Name are preserved"""
    data = {
        "data": {
            "success": True,
            "data": [
                ["Area Name", "Code", "GeoID"],
                ["Aberdeen, SD Micro Area", "10100", "310M700US10100"],
            ],
        }
    }
    df = _create_dataframe_from_json(data)
    assert df["Area Name"].dtype == object
    assert df["Area Name"].iloc[0] == "Aberdeen, SD Micro Area"
    assert df["GeoID"].dtype == object
    assert df["GeoID"].iloc[0] == "310M700US10100"
