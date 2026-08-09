from __future__ import annotations

from unittest.mock import MagicMock

from app import create_census_graph
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.domain.geography_catalog import AreaCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.services.geography_clarification_resume import resume_geography_clarification
from src.services.graph_session import build_turn_state_for_thread, runnable_config
from src.services.memory_utils import update_profile
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


class AmbiguousAreaRetrieval(FakeGroundedRetrieval):
    def retrieve_geographies(self, analysis, *, dataset: str, year: int) -> GeographyRetrievalResult:
        result = super().retrieve_geographies(analysis, dataset=dataset, year=year)
        original = result.area_evidence[0]
        illinois = AreaCandidate(
            candidate_id="area:illinois",
            dataset=dataset,
            year=year,
            display_name="Illinois",
            score=0.985,
            provenance="census_api",
            schema_version="1.0",
            friendly_level="state",
            census_token="state",
            geo_id="0400000US17",
            geography_code="17",
        )
        return GeographyRetrievalResult(
            hierarchy_evidence=result.hierarchy_evidence,
            area_evidence=[
                RetrievalEvidence(
                    evidence_id=original.evidence_id,
                    collection_name=original.collection_name,
                    status="hit",
                    query_text=original.query_text,
                    index_version=original.index_version,
                    schema_version=original.schema_version,
                    candidate_ids=[original.candidates[0].candidate_id, illinois.candidate_id],
                    candidates=[original.candidates[0], illinois],
                )
            ],
        )


def _pending_plan():
    question = "Show total population for Springfield counties in 2023"
    from src.services.graph_session import build_fresh_thread_state

    state = build_fresh_thread_state(question)
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    fake = AmbiguousAreaRetrieval()
    result = geography_node(state, {}, dependencies=fake.dependencies())
    return result["plan"], result["final"]


def test_pending_context_contains_trace_evidence_and_only_official_labels():
    plan, final = _pending_plan()
    pending = plan.pending_geography_clarification
    assert pending is not None
    assert pending.original_query == "Show total population for Springfield counties in 2023"
    assert pending.trace_id == plan.retrieval_trace.trace_id
    assert pending.requested_slot == "area"
    assert pending.index_version == "1.0"
    assert pending.retrieved_candidate_ids == ["area:california", "area:illinois"]
    assert [option.label for option in pending.options] == ["California", "Illinois"]
    assert "Springfield" not in final["answer_text"]
    assert final["clarification_type"] == "geography"
    assert final["reason_code"] == "GEOGRAPHY_AMBIGUOUS"
    assert final["trace_id"] == pending.trace_id


def test_resume_accepts_option_id_or_natural_language_and_revalidates_evidence():
    plan, _final = _pending_plan()
    by_id = resume_geography_clarification(plan, "geo_0")
    assert by_id.status == "resolved"
    assert by_id.geography.display_name == "California"
    assert by_id.plan.grounded_plan.geography.area_candidate_ids == ["area:california"]

    by_name = resume_geography_clarification(plan, "Illinois")
    assert by_name.status == "resolved"
    assert by_name.geography.display_name == "Illinois"
    assert by_name.plan.grounded_plan.geography.area_candidate_ids == ["area:illinois"]


def test_resume_rejects_multi_select_and_supports_cancel():
    plan, _final = _pending_plan()
    rejected = resume_geography_clarification(plan, "all of them")
    assert rejected.status == "clarification_required"
    assert rejected.plan.pending_geography_clarification is not None

    cancelled = resume_geography_clarification(plan, "cancel")
    assert cancelled.status == "cancelled"
    assert cancelled.plan.pending_geography_clarification is None
    assert cancelled.plan.workflow_cancelled is True


def test_resume_rejects_option_metadata_that_does_not_match_preserved_evidence():
    plan, _final = _pending_plan()
    tampered = plan.model_copy(deep=True)
    tampered.pending_geography_clarification.options[0].label = "Invented label"
    result = resume_geography_clarification(tampered, "geo_0")
    assert result.status == "clarification_required"
    assert result.geography is None


def test_checkpoint_second_turn_preserves_pending_plan_and_original_query():
    plan, _final = _pending_plan()
    graph = MagicMock()
    graph.get_state.return_value = MagicMock(
        values={
            "messages": [{"role": "user", "content": plan.pending_geography_clarification.original_query}],
            "plan": plan,
        }
    )
    config = runnable_config(user_id="phase5", thread_id="thread")
    state = build_turn_state_for_thread(graph, "Illinois", config=config)
    assert state.messages[-1]["content"] == "Illinois"
    assert state.original_query == plan.pending_geography_clarification.original_query
    assert state.plan.pending_geography_clarification.trace_id == plan.pending_geography_clarification.trace_id


def test_checkpointed_graph_resumes_selection_instead_of_analyzing_it_as_fresh_query(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CENSUS_CHECKPOINT_DB", str(tmp_path / "phase5.db"))

    class FakeAgent:
        offline_mode = False

        def __init__(self, mode="execution", allow_offline=True):
            self.mode = mode

        def solve(self, **kwargs):
            if self.mode == "planning" or kwargs.get("clarification_context") is not None:
                return {
                    "reasoning_trace": "fake planning/clarification",
                    "data_summary": "checkpoint resume",
                    "answer_text": "fake planning",
                }
            return {
                "answer_text": "Resumed Illinois result.",
                "census_data": {"success": False, "data": []},
                "data_summary": "checkpoint resume",
                "reasoning_trace": "fake",
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [],
            }

        def compose_clarification_prompt(self, _ctx):
            return {"answer_text": "Which geography should I use?"}

    monkeypatch.setattr("src.workflows.agent_planning.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent_clarification_prompt.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent_clarification_resume.CensusQueryAgent", FakeAgent)
    monkeypatch.setattr("src.workflows.agent.CensusQueryAgent", FakeAgent)

    graph = create_census_graph()
    config = runnable_config(user_id="phase5-multiturn", thread_id="phase5-thread")
    fake = AmbiguousAreaRetrieval()
    config["configurable"]["grounded_geography_dependencies"] = fake.dependencies()

    turn1_state = build_turn_state_for_thread(
        graph,
        "Show total population for Springfield counties in 2023",
        config=config,
    )
    turn1 = graph.invoke(turn1_state, config)
    trace_id = turn1["plan"].pending_geography_clarification.trace_id

    turn2_state = build_turn_state_for_thread(graph, "Illinois", config=config)
    turn2 = graph.invoke(turn2_state, config)

    assert turn2["geo"].display_name == "Illinois"
    assert turn2["plan"].pending_geography_clarification is None
    assert turn2["plan"].retrieval_trace.trace_id == trace_id
    assert [call for call in fake.calls if call[0] == "analyze"] == [
        ("analyze", "Show total population for Springfield counties in 2023")
    ]


def test_memory_persists_grounded_ids_and_display_text_without_filters():
    plan, _final = _pending_plan()
    resumed = resume_geography_clarification(plan, "Illinois")
    geo = resumed.geography.model_dump()
    profile = update_profile({}, {}, geo, {"answer_text": "ok"}, resumed.plan)
    assert profile["default_geo"] == {
        "candidate_ids": ["hierarchy:county", "area:illinois"],
        "display_name": "Illinois",
    }
    assert "geo_for" not in profile["default_geo"]
    assert "geo_in" not in profile["default_geo"]


def test_legacy_memory_filters_are_dropped_and_display_remains_untrusted_hint():
    profile = {
        "default_geo": {
            "display_name": "Legacy place",
            "geo_for": {"place": "12345"},
            "geo_in": {"state": "99"},
        }
    }
    updated = update_profile(profile, {}, {}, {})
    assert updated["default_geo"] == {"display_name": "Legacy place"}
