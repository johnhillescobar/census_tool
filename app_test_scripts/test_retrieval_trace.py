import pytest

from src.clients import telemetry
from src.domain.retrieval_trace import (
    RetrievalCandidateTrace,
    RetrievalStage,
    RetrievalStatus,
    RetrievalTrace,
    RetrievalTraceEvent,
)
from src.state.workflow_plan import WorkflowPlan


def test_retrieval_trace_round_trips_through_workflow_plan():
    trace = RetrievalTrace(prompt_version="test.v1")
    trace.append(
        RetrievalTraceEvent(
            stage=RetrievalStage.GEOGRAPHY_RETRIEVAL,
            status=RetrievalStatus.HIT,
            collection="census_geography_areas",
            filters={"year": 2023},
            candidates=[
                RetrievalCandidateTrace(
                    candidate_id="state:06",
                    score=0.99,
                    display_name="California",
                )
            ],
            selected_ids=["state:06"],
            index_version="test-index",
        )
    )

    restored = WorkflowPlan.model_validate(WorkflowPlan(retrieval_trace=trace).model_dump(mode="json")).retrieval_trace

    assert restored is not None
    assert restored.trace_id == trace.trace_id
    assert restored.compact_summary() == ["geography_retrieval:hit"]


def test_retrieval_trace_rejects_unknown_fields():
    event = {
        "stage": "analysis",
        "status": "started",
        "unexpected": "not allowed",
    }

    try:
        RetrievalTraceEvent.model_validate(event)
    except ValueError:
        return
    raise AssertionError("RetrievalTraceEvent accepted an unknown field")


def test_telemetry_strict_mode_surfaces_write_failures(monkeypatch, capsys):
    def fail_write(_message: str) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setenv("CENSUS_TELEMETRY_STRICT", "1")
    monkeypatch.setattr(telemetry._logger, "info", fail_write)

    with pytest.raises(OSError, match="disk unavailable"):
        telemetry.record_event("test_event", {"trace_id": "trace"})

    assert "telemetry_write_failed" in capsys.readouterr().err
