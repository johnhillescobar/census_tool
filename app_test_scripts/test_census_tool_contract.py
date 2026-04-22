import pytest

from src.domain.census_tool_contract import (
    StrictCensusApiRawTable,
    StrictCensusApiRecord,
    StrictCensusApiRequest,
    StrictCensusApiResponse,
)


def _valid_request() -> StrictCensusApiRequest:
    return StrictCensusApiRequest(
        year=2023,
        dataset="acs/acs5",
        variables=["NAME", "B01003_001E"],
        geo_for={"state": "*"},
        geo_in={"region": "1"},
        geo_in_chained=[{"division": "2"}],
    )


def test_request_normalizes_variables_and_geo_fields() -> None:
    req = StrictCensusApiRequest(
        year=2023,
        dataset="acs/acs5",
        variables=[" NAME ", "B01003_001E "],
        geo_for={" state ": " * "},
        geo_in={" region ": " 1 "},
        geo_in_chained=[{" division ": " 2 "}],
    )

    assert req.variables == ["NAME", "B01003_001E"]
    assert req.geo_for == {"state": "*"}
    assert req.geo_in == {"region": "1"}
    assert req.geo_in_chained == [{"division": "2"}]


def test_request_rejects_blank_variable_entries() -> None:
    with pytest.raises(ValueError, match="variables must not contain blank entries"):
        StrictCensusApiRequest(
            year=2023,
            dataset="acs/acs5",
            variables=["NAME", "   "],
            geo_for={"state": "*"},
        )


def test_request_rejects_duplicate_variables_after_normalization() -> None:
    with pytest.raises(ValueError, match="variables must be unique"):
        StrictCensusApiRequest(
            year=2023,
            dataset="acs/acs5",
            variables=["NAME", " NAME "],
            geo_for={"state": "*"},
        )


def test_request_rejects_empty_geo_in_chained_entry() -> None:
    with pytest.raises(
        ValueError, match="geo_in_chained entries must be non-empty dicts"
    ):
        StrictCensusApiRequest(
            year=2023,
            dataset="acs/acs5",
            variables=["NAME"],
            geo_for={"state": "*"},
            geo_in_chained=[{}],
        )


def test_raw_table_rejects_row_width_mismatch() -> None:
    with pytest.raises(ValueError, match="rows must have the same length"):
        StrictCensusApiRawTable(
            headers=["NAME", "state"],
            rows=[["California", "06"], ["Nevada"]],
        )


def test_success_response_requires_clean_error_fields() -> None:
    request = _valid_request()
    records = [
        StrictCensusApiRecord(values={"NAME": "California", "state": "06"}),
    ]
    response = StrictCensusApiResponse(
        success=True,
        request=request,
        headers=["NAME", "state"],
        records=records,
        row_count=1,
        error=None,
        error_message=None,
    )

    assert response.success is True
    assert response.row_count == 1


def test_success_response_rejects_error_code() -> None:
    with pytest.raises(ValueError, match="error must be None when success is True"):
        StrictCensusApiResponse(
            success=True,
            request=_valid_request(),
            headers=["NAME", "state"],
            records=[
                StrictCensusApiRecord(values={"NAME": "California", "state": "06"})
            ],
            row_count=1,
            error="API_HTTP_ERROR",
            error_message=None,
        )


def test_failure_response_requires_error_code_and_empty_data() -> None:
    with pytest.raises(ValueError, match="error is required when success is False"):
        StrictCensusApiResponse(
            success=False,
            request=_valid_request(),
            headers=[],
            records=[],
            row_count=0,
            error=None,
            error_message=None,
        )


def test_failure_response_fills_default_error_message() -> None:
    response = StrictCensusApiResponse(
        success=False,
        request=_valid_request(),
        headers=[],
        records=[],
        row_count=0,
        error="EMPTY_RESULT",
        error_message=None,
    )

    assert response.error == "EMPTY_RESULT"
    assert response.error_message == "The result is empty"
