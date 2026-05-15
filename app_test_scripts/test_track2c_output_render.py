"""Track 2C: output_node render failures as typed artifacts."""

from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableConfig

from src.domain.census_tool_contract import StrictCensusApiResponse, no_strict_census_payload
from src.domain.final_output_contract import FinalChartSpec, FinalTableSpec
from src.domain.rendered_output_contract import RenderedArtifactFailure, RENDER_ERROR_NO_TABULAR_DATA, RENDER_ERROR_RENDER_EXCEPTION
from src.state.types import CensusState, FinalResponseState, WorkflowArtifactsState
from src.tools.chart_tool import ChartTool
from src.workflows.output import output_node


def _strict_census_with_numeric_variable() -> StrictCensusApiResponse:
    return StrictCensusApiResponse.model_validate(
        {
            "success": True,
            "request": {
                "year": 2023,
                "dataset": "acs/acs5",
                "variables": ["NAME", "B01003_001E"],
                "geo_for": {"place": "44000"},
                "geo_in": {"state": "06"},
                "geo_in_chained": [],
            },
            "headers": ["NAME", "B01003_001E"],
            "records": [{"values": {"NAME": "Los Angeles", "B01003_001E": "100"}}],
            "row_count": 1,
            "error": None,
            "error_message": None,
        }
    )


def test_output_node_no_tabular_failure_for_chart_and_table(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    state = CensusState(
        artifacts=WorkflowArtifactsState(
            census_data=no_strict_census_payload(),
        ),
        final=FinalResponseState(
            answer_text="ok",
            charts_needed=[FinalChartSpec(type="bar", title="C1")],
            tables_needed=[
                FinalTableSpec(format="csv", filename="t", title="Table 1"),
            ],
        ),
    )

    delta = output_node(state, RunnableConfig())

    gfs = FinalResponseState.model_validate(delta["final"]).generated_files
    assert len(gfs) == 2
    assert all(isinstance(a, RenderedArtifactFailure) for a in gfs)
    assert gfs[0].error_code == RENDER_ERROR_NO_TABULAR_DATA
    assert gfs[1].kind == "table"


def test_output_node_chart_exception_surfaces(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def _boom_render(self, tool_input):
        raise RuntimeError("render boom")

    monkeypatch.setattr(ChartTool, "render", _boom_render)

    state = CensusState(
        artifacts=WorkflowArtifactsState(
            census_data=_strict_census_with_numeric_variable(),
        ),
        final=FinalResponseState(
            charts_needed=[FinalChartSpec(type="bar", title="Pop")],
        ),
    )

    delta = output_node(state, RunnableConfig())

    gfs = FinalResponseState.model_validate(delta["final"]).generated_files
    assert len(gfs) == 1
    failure = gfs[0]
    assert isinstance(failure, RenderedArtifactFailure)
    assert failure.error_code == RENDER_ERROR_RENDER_EXCEPTION
    assert "render boom" in failure.message


def test_final_response_generated_files_backward_compat_without_status_field():
    fr = FinalResponseState.model_validate(
        {
            "answer_text": "x",
            "generated_files": [
                {"kind": "chart", "path": "/tmp/x.png", "mime_type": "image/png"}
            ],
        }
    )
    row = fr.generated_files[0]
    assert row.status == "success"
    assert row.path == "/tmp/x.png"

