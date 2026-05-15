"""Tests for the contract-first CLI display surface (typed ``CensusState`` only)."""

from io import StringIO
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.api.displays import census_state_from_graph_invoke, display_results
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.rendered_output_contract import (
    RenderedArtifact,
    RenderedArtifactFailure,
)
from src.state.types import CensusState, FinalResponseState


def _render_state(state: CensusState) -> str:
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_results(state)
        return fake_out.getvalue()


def test_display_results_renders_typed_final_response():
    final = FinalResponseState(
        answer_text="The population of New York City is 8,804,190.",
        generated_files=[
            RenderedArtifact(
                kind="chart",
                path="data/charts/nyc_population.png",
                mime_type="image/png",
                title="NYC Population Chart",
            ),
            RenderedArtifact(
                kind="table",
                path="data/tables/nyc_population.csv",
                mime_type="text/csv",
                title="NYC Population Table",
            ),
            RenderedArtifactFailure(
                status="failure",
                kind="chart",
                error_code="NO_TABULAR_DATA",
                message="No tabular census rows available for chart rendering.",
                title=None,
            ),
        ],
        charts_needed=[FinalChartSpec(type="bar", title="Population by Borough")],
        tables_needed=[
            FinalTableSpec(
                format="csv",
                filename="nyc_population.csv",
                title="NYC Population Export",
            )
        ],
        footnotes=["Data from ACS 5-Year Estimates, 2023"],
    )

    state = census_state_from_graph_invoke(
        {
            "messages": [{"role": "user", "content": "Population of NYC"}],
            "final": final,
            "logs": ["data: processed 1 queries successfully"],
        }
    )

    output = _render_state(state)

    assert "CENSUS DATA RESULTS" in output
    assert "The population of New York City is 8,804,190." in output
    assert "[FILES GENERATED]: 3 artifact(s)" in output
    assert "NYC Population Chart" in output
    assert "nyc_population.csv" in output
    assert "[RENDER FAILED]" in output
    assert "NO_TABULAR_DATA" in output
    assert "[CHARTS REQUESTED]: 1 chart(s)" in output
    assert "Bar chart: Population by Borough" in output
    assert "[TABLES REQUESTED]: 1 table(s)" in output
    assert "CSV table: nyc_population.csv" in output
    assert "Footnotes:" in output
    assert "System Logs:" in output


def test_display_results_invoke_shaped_state():
    state = census_state_from_graph_invoke(
        {
            "messages": [],
            "final": {
                "answer_text": "California population answer.",
                "generated_files": [],
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [],
            },
        }
    )
    output = _render_state(state)

    assert "CENSUS DATA RESULTS" in output
    assert "[ANSWER] California population answer." in output


def test_display_results_with_error():
    state = CensusState(error="No data found for the specified criteria")
    output = _render_state(state)

    assert "[ERROR] Error:" in output
    assert "No data found" in output


def test_display_results_with_missing_final():
    output = _render_state(CensusState())

    assert "[ERROR] No answer available" in output


def test_census_state_adapter_rejects_invalid_final_shape():
    with pytest.raises(ValidationError):
        census_state_from_graph_invoke(
            {
                "messages": [],
                "final": {
                    "answer_text": "This should be rejected",
                    "generated_files": "not-a-list",
                },
            }
        )
