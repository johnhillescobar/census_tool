"""Tests for the contract-first CLI display surface."""

from io import StringIO
from unittest.mock import patch

from src.api import display_results
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.rendered_output_contract import RenderedArtifact
from src.state.types import FinalResponseState


def _render_output(result: dict) -> str:
    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_results(result)
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

    output = _render_output(
        {
            "final": final,
            "logs": ["data: processed 1 queries successfully"],
        }
    )

    assert "CENSUS DATA RESULTS" in output
    assert "The population of New York City is 8,804,190." in output
    assert "[FILES GENERATED]: 2 file(s)" in output
    assert "NYC Population Chart" in output
    assert "nyc_population.csv" in output
    assert "[CHARTS REQUESTED]: 1 chart(s)" in output
    assert "Bar chart: Population by Borough" in output
    assert "[TABLES REQUESTED]: 1 table(s)" in output
    assert "CSV table: nyc_population.csv" in output
    assert "Footnotes:" in output
    assert "System Logs:" in output


def test_display_results_accepts_dict_final_response():
    output = _render_output(
        {
            "final": {
                "answer_text": "California population answer.",
                "generated_files": [],
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [],
            }
        }
    )

    assert "CENSUS DATA RESULTS" in output
    assert "[ANSWER] California population answer." in output


def test_display_results_with_error():
    output = _render_output(
        {"error": "No data found for the specified criteria", "final": None}
    )

    assert "[ERROR] Error:" in output
    assert "No data found" in output


def test_display_results_with_missing_final():
    output = _render_output({"final": None})

    assert "[ERROR] No answer available" in output


def test_display_results_with_invalid_final_shape():
    output = _render_output(
        {
            "final": {
                "answer_text": "This should be rejected",
                "generated_files": "not-a-list",
            }
        }
    )

    assert "[ERROR] No answer available" in output
