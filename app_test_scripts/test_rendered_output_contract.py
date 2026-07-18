from io import StringIO
from unittest.mock import patch

from src.api.displays import display_results
from src.domain.presentation_contract import PresentationKind
from src.domain.rendered_output_contract import (
    RenderedArtifactFailure,
    RenderedArtifactSuccess,
    artifact_from_tool_result,
)
from src.services.presentation_routing import compute_presentation_routing
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan


def test_artifact_from_tool_result_parses_chart_success() -> None:
    artifact = artifact_from_tool_result(
        "Chart created successfully: data/charts/example.png",
        kind="chart",
        title="Example",
    )

    assert isinstance(artifact, RenderedArtifactSuccess)
    assert artifact.path == "data/charts/example.png"
    assert artifact.title == "Example"


def test_artifact_from_tool_result_parses_chart_html_success() -> None:
    artifact = artifact_from_tool_result(
        "Chart saved as HTML: data/charts/chart_bar_123.html",
        kind="chart",
        title="Fallback",
    )

    assert isinstance(artifact, RenderedArtifactSuccess)
    assert artifact.path == "data/charts/chart_bar_123.html"
    assert artifact.mime_type == "text/html"
    assert artifact.title == "Fallback"


def test_artifact_from_tool_result_table_xlsx_mime_type() -> None:
    artifact = artifact_from_tool_result(
        "Table created successfully: data/tables/report.xlsx",
        kind="table",
    )

    assert isinstance(artifact, RenderedArtifactSuccess)
    assert artifact.mime_type == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_artifact_from_tool_result_table_html_mime_type() -> None:
    artifact = artifact_from_tool_result(
        "Table created successfully: data/tables/report.html",
        kind="table",
    )

    assert isinstance(artifact, RenderedArtifactSuccess)
    assert artifact.mime_type == "text/html"


def test_artifact_from_tool_result_preserves_failure() -> None:
    artifact = artifact_from_tool_result("boom", kind="table")

    assert isinstance(artifact, RenderedArtifactFailure)
    assert artifact.error_code == "RENDER_EXCEPTION"
    assert artifact.message == "boom"


def test_display_results_formats_typed_generated_artifacts() -> None:
    result = {
        "final": {
            "answer_text": "Done",
            "generated_files": [
                RenderedArtifactSuccess(
                    kind="chart",
                    path="data/charts/example.png",
                    mime_type="image/png",
                ).model_dump()
            ],
        }
    }

    with patch("sys.stdout", new=StringIO()) as fake_out:
        display_results(result)

    assert "Chart created successfully: data/charts/example.png" in fake_out.getvalue()


def test_presentation_routing_uses_current_state_shape() -> None:
    state = CensusState(
        messages=[{"role": "user", "content": "Population"}],
        original_query=None,
        intent=None,
        plan=WorkflowPlan(requires_clarification=False),
        final={"answer_text": "Population result"},
        artifacts={
            "census_data": {
                "success": True,
                "data": [["NAME", "B01003_001E"], ["California", "39538223"]],
            }
        },
        error=None,
        summary=None,
    )

    routing = compute_presentation_routing(state)

    assert routing.kind == PresentationKind.SINGLE_VALUE
