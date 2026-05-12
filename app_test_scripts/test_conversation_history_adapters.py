"""Tests for Streamlit/PDF conversation history helpers (strict PdfConversationEntry shape)."""

from datetime import datetime

import pytest
from pydantic_core import ValidationError

from src.clients.pdf_generator import PdfConversationEntry
from src.domain.presentation_contract import PresentationKind
from src.domain.census_tool_contract import no_strict_census_payload
from src.services.conversation_history import (
    census_state_from_pdf_history_entry,
    history_entry_presentation_kind,
    infer_streamlit_line_xy,
    pdf_conversation_result_dict,
)
from src.state.types import CensusState, FinalResponseState, WorkflowArtifactsState


def _minimal_result_dict() -> dict:
    return {
        "final": {
            "answer_text": "Answer",
            "generated_files": [],
            "footnotes": [],
            "charts_needed": [],
            "tables_needed": [],
        },
        "artifacts": _minimal_artifacts_dict(),
        "logs": [],
        "error": None,
    }


def _minimal_artifacts_dict() -> dict:
    return {
        "census_data": None,
        "variable_labels": {"labels": {}},
        "data_summary": "",
        "reasoning_trace": "",
        "comparison_input_rows": [],
        "comparison_metrics": [],
    }


def _minimal_strict_census_dict_one_row() -> dict:
    return {
        "success": True,
        "request": {
            "year": 2020,
            "dataset": "acs/acs5",
            "variables": ["B01003_001E"],
            "geo_for": {"place": "44000"},
            "geo_in": {"state": "06"},
            "geo_in_chained": [],
        },
        "headers": ["NAME", "B01003_001E"],
        "records": [
            {"values": {"NAME": "Los Angeles", "B01003_001E": "100"}},
        ],
        "row_count": 1,
        "error": None,
        "error_message": None,
    }


def _history_entry_with_artifacts(artifacts: dict) -> dict:
    return {
        "question": "q",
        "timestamp": datetime.now(),
        "result": {
            "artifacts": artifacts,
            "logs": [],
            "error": None,
        },
    }


def _minimal_final_dict(*, generated_files) -> dict:
    return {
        "answer_text": "Answer",
        "generated_files": generated_files,
        "footnotes": [],
        "charts_needed": [],
        "tables_needed": [],
    }


def _result_dict_with_final(final: dict) -> dict:
    return {
        "final": final,
        "artifacts": _minimal_artifacts_dict(),
        "logs": [],
        "error": None,
    }


def _history_entry_with_generated_files(generated_files) -> dict:
    return {
        "question": "q",
        "timestamp": datetime.now(),
        "result": _result_dict_with_final(_minimal_final_dict(generated_files=generated_files)),
    }


@pytest.mark.parametrize(
    "bad_generated_files",
    [
        pytest.param("not-a-list", id="generated_files_scalar_string"),
        pytest.param(
            ["Chart created successfully: data/charts/chart_bar.png"],
            id="generated_files_list_of_strings",
        ),
        pytest.param(
            [{"kind": "chart", "path": "/fake/path.png"}],
            id="rendered_artifact_missing_mime_type",
        ),
        pytest.param(
            [
                {
                    "kind": "chart",
                    "path": "/fake/path.png",
                    "mime_type": "image/png",
                    "junk_key": True,
                }
            ],
            id="rendered_artifact_extra_key",
        ),
    ],
)
def test_final_response_generated_files_rejects_regressions(bad_generated_files) -> None:
    final_dict = _minimal_final_dict(generated_files=bad_generated_files)
    with pytest.raises(ValidationError):
        FinalResponseState.model_validate(final_dict)
    with pytest.raises(ValidationError):
        PdfConversationEntry.model_validate(
            _history_entry_with_generated_files(bad_generated_files)
        )
    with pytest.raises(ValidationError):
        census_state_from_pdf_history_entry(
            _history_entry_with_generated_files(bad_generated_files)
        )


@pytest.mark.parametrize(
    "bad_artifacts",
    [
        pytest.param(
            {**_minimal_artifacts_dict(), "ghost_top_level": 1},
            id="artifacts_extra_top_level_key",
        ),
        pytest.param(
            {
                **_minimal_artifacts_dict(),
                "variable_labels": {"labels": {}, "illegitimate": True},
            },
            id="variable_labels_extra_key",
        ),
        pytest.param(
            {
                **_minimal_artifacts_dict(),
                "census_data": {**_minimal_strict_census_dict_one_row(), "noise": 1},
            },
            id="census_data_extra_top_level_key",
        ),
        pytest.param(
            {
                **_minimal_artifacts_dict(),
                "comparison_input_rows": [
                    {
                        "year": 2023,
                        "geo_id": "g",
                        "metric": "m",
                        "value": 1.0,
                        "benchmark_value": 2.0,
                        "extra_col": True,
                    }
                ],
            },
            id="comparison_input_row_extra_key",
        ),
        pytest.param(
            {
                **_minimal_artifacts_dict(),
                "comparison_metrics": [
                    {
                        "year": 2023,
                        "geo_id": "g",
                        "metric": "m",
                        "derived_metric": "difference",
                        "value": 1.0,
                        "bogus": "x",
                    }
                ],
            },
            id="comparison_metric_row_extra_key",
        ),
        pytest.param(
            {**_minimal_artifacts_dict(), "data_summary": 99},
            id="data_summary_wrong_type",
        ),
        pytest.param(
            {**_minimal_artifacts_dict(), "reasoning_trace": []},
            id="reasoning_trace_wrong_type",
        ),
    ],
)
def test_workflow_artifacts_rejects_dict_regressions(bad_artifacts: dict) -> None:
    with pytest.raises(ValidationError):
        WorkflowArtifactsState.model_validate(bad_artifacts)
    with pytest.raises(ValidationError):
        census_state_from_pdf_history_entry(_history_entry_with_artifacts(bad_artifacts))


def test_pdf_conversation_entry_accepts_strict_history_shape() -> None:
    payload = {
        "question": "What is population?",
        "timestamp": datetime.now(),
        "result": _minimal_result_dict(),
    }
    entry = PdfConversationEntry.model_validate(payload)
    assert entry.question.startswith("What")
    assert entry.result is not None
    assert entry.result.final is not None
    assert entry.result.final.answer_text == "Answer"


def test_pdf_conversation_entry_rejects_extra_top_level_keys() -> None:
    payload = {
        "question": "Q",
        "timestamp": datetime.now(),
        "answer_text": "duplicate",
        "generated_files": [],
        "result": _minimal_result_dict(),
    }
    with pytest.raises(ValidationError):
        PdfConversationEntry.model_validate(payload)


def test_history_entry_time_series_routing() -> None:
    census_data = {
        "success": True,
        "request": {
            "year": 2020,
            "dataset": "acs/acs5",
            "variables": ["B01003_001E"],
            "geo_for": {"place": "44000"},
            "geo_in": {"state": "06"},
            "geo_in_chained": [],
        },
        "headers": ["NAME", "year", "B01003_001E"],
        "records": [
            {
                "values": {
                    "NAME": "Los Angeles",
                    "year": "2019",
                    "B01003_001E": "100",
                }
            },
            {
                "values": {
                    "NAME": "Los Angeles",
                    "year": "2020",
                    "B01003_001E": "101",
                }
            },
        ],
        "row_count": 2,
        "error": None,
        "error_message": None,
    }
    entry = {
        "question": "Trend?",
        "timestamp": datetime.now(),
        "result": {
            "final": {
                "answer_text": "Here is the trend.",
                "generated_files": [],
                "footnotes": [],
                "charts_needed": [],
                "tables_needed": [],
            },
            "artifacts": {
                "census_data": census_data,
                "variable_labels": {"labels": {"B01003_001E": "Population"}},
                "data_summary": "",
                "reasoning_trace": "",
                "comparison_input_rows": [],
                "comparison_metrics": [],
            },
            "logs": [],
            "error": None,
        },
    }
    assert history_entry_presentation_kind(entry) == PresentationKind.TIME_SERIES


def test_pdf_conversation_result_dict_round_trip() -> None:
    state = CensusState(
        messages=[],
        original_query="oq",
        intent=None,
        geo={},
        candidates={},
        plan=None,
        artifacts=WorkflowArtifactsState(),
        final=FinalResponseState(answer_text="Hello"),
        logs=["one"],
        error=None,
        summary=None,
        profile={},
        history=[],
        cache_index={},
    )
    payload = pdf_conversation_result_dict(state)
    entry = {
        "question": "q",
        "timestamp": datetime.now(),
        "result": payload,
    }
    restored = census_state_from_pdf_history_entry(entry)
    assert restored.final is not None
    assert restored.final.answer_text == "Hello"
    assert restored.logs == ["one"]


def test_infer_streamlit_line_xy_prefers_yearish_and_variable() -> None:
    import pandas as pd

    df = pd.DataFrame(
        {
            "NAME": ["A", "A"],
            "year": [2019, 2020],
            "B01003_001E": [1, 2],
        }
    )
    x, y = infer_streamlit_line_xy(df, no_strict_census_payload())
    assert x.lower() == "year"
    assert y == "B01003_001E"
