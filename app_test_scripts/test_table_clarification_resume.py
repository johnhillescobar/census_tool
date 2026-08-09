"""Table-slot resume must continue geography planning after a grounded table pick."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app import _route_after_memory
from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.domain.geography_catalog import TableCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.agent_plan_context import build_agent_clarification_context
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis
from src.services.graph_session import build_fresh_thread_state
from src.workflows.agent_clarification_resume import agent_clarification_resume_node
from src.workflows.agent_planning import agent_planning_node
from src.workflows.geography import geography_node, geography_resume_node
from src.workflows.temporal import temporal_node

ROW_3_QUESTION = "Show total population for all California counties in 2023."


class ChromaShapedRow3Retrieval(FakeGroundedRetrieval):
    """Mirror live Chroma: housing tables outscore B01001 on a thin margin."""

    def retrieve_tables(self, analysis: CensusRetrievalAnalysis, *, year: int) -> RetrievalEvidence:
        self.calls.append(("table", year))
        housing = TableCandidate(
            candidate_id="table:acs/acs5:B25008",
            dataset="acs/acs5",
            year=year,
            display_name="TOTAL POPULATION IN OCCUPIED HOUSING UNITS BY TENURE",
            score=0.5196,
            provenance="census_groups",
            schema_version="1.0",
            table_code="B25008",
            table_name="TOTAL POPULATION IN OCCUPIED HOUSING UNITS BY TENURE",
            category="detail",
            years_available=[year],
        )
        housing_close = TableCandidate(
            candidate_id="table:acs/acs5:B25033",
            dataset="acs/acs5",
            year=year,
            display_name="TOTAL POPULATION IN OCCUPIED HOUSING UNITS BY TENURE BY UNITS IN STRUCTURE",
            score=0.5012,
            provenance="census_groups",
            schema_version="1.0",
            table_code="B25033",
            table_name="TOTAL POPULATION IN OCCUPIED HOUSING UNITS BY TENURE BY UNITS IN STRUCTURE",
            category="detail",
            years_available=[year],
        )
        canonical = TableCandidate(
            candidate_id="table:acs/acs5:B01001",
            dataset="acs/acs5",
            year=year,
            display_name="SEX BY AGE",
            score=0.43,
            provenance="census_groups",
            schema_version="1.0",
            table_code="B01001",
            table_name="SEX BY AGE",
            category="detail",
            years_available=[year],
        )
        candidates = [housing, housing_close, canonical]
        return RetrievalEvidence(
            evidence_id="table-evidence",
            collection_name="census_tables",
            status=self.table_status,
            query_text=analysis.table_search_text,
            index_version="1.0",
            schema_version="1.0",
            candidate_ids=[candidate.candidate_id for candidate in candidates],
            candidates=candidates,
        )


def _turn1_state(question: str = ROW_3_QUESTION):
    state = build_fresh_thread_state(question)
    temporal = temporal_node(state, {})
    return state.model_copy(update={"plan": temporal["plan"]})


def _resume_turn2(plan, selection: str, fake: FakeGroundedRetrieval, *, use_agent_path: bool = True):
    resume_state = _turn1_state().model_copy(update={"plan": plan, "messages": [{"role": "user", "content": selection}]})
    config = {"configurable": {"grounded_geography_dependencies": fake.dependencies()}}
    if use_agent_path:
        return agent_clarification_resume_node(resume_state, config)
    return geography_resume_node(resume_state, config)


def test_route_after_memory_routes_pending_clarification_to_agent_resume():
    turn1 = geography_node(_turn1_state(), {}, dependencies=AmbiguousTablesFake().dependencies())
    state = _turn1_state().model_copy(update={"plan": turn1["plan"]})
    assert _route_after_memory(state) == "agent_clarification_resume"


def test_build_agent_clarification_context_exposes_checkpoint_contract():
    turn1 = geography_node(_turn1_state(), {}, dependencies=AmbiguousTablesFake().dependencies())
    plan = turn1["plan"]
    pending = plan.pending_geography_clarification
    assert pending is not None

    context = build_agent_clarification_context(plan)
    assert context is not None
    assert context.original_query == pending.original_query
    assert context.requested_slot == pending.requested_slot
    assert context.pending_options == pending.options
    assert context.retrieval_evidence == plan.retrieval_evidence
    assert context.reason_code == pending.reason_code
    assert context.trace_id == pending.trace_id
    assert context.turn1_prompt_text is None


@patch("src.workflows.agent_planning.CensusQueryAgent")
def test_build_agent_clarification_context_restores_turn1_prompt_from_checkpoint(mock_agent_cls, monkeypatch):
    import config as config_module

    monkeypatch.setattr(config_module, "CENSUS_AGENT_TURN1_PLANNING", True)
    import src.workflows.geography as geography_module

    monkeypatch.setattr(geography_module, "CENSUS_AGENT_TURN1_PLANNING", True)
    mock_agent_cls.return_value.offline_mode = True

    state = _turn1_state()
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    turn1 = geography_node(state, {}, dependencies=AmbiguousTablesFake().dependencies())
    state = state.model_copy(update={"plan": turn1["plan"]})
    clarify = agent_planning_node(state, {})
    plan = clarify["plan"]

    context = build_agent_clarification_context(plan)
    assert context is not None
    assert context.turn1_prompt_text is not None
    assert "SEX BY AGE (B01001)" in context.turn1_prompt_text


def _agent_tool_step(plan, option_id: str):
    pending = plan.pending_geography_clarification
    assert pending is not None
    option = next(item for item in pending.options if item.option_id == option_id)
    payload = (
        f'{{"status": "accepted", "option_id": "{option.option_id}", '
        f'"candidate_id": "{option.candidate_id}", "label": "{option.label}"}}'
    )
    return (MagicMock(tool="select_clarification_option"), payload)


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_table_resume_resolves_geography_after_ambiguous_table_pick(mock_agent_cls):
    fake = AmbiguousTablesFake()
    turn1 = geography_node(_turn1_state(), {}, dependencies=fake.dependencies())
    plan = turn1["plan"]
    pending = plan.pending_geography_clarification
    assert pending is not None
    assert pending.requested_slot == "table"

    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Clarification tool steps: 1 (select_clarification_option)",
        "data_summary": "User selected table_0.",
        "answer_text": "Proceeding with SEX BY AGE.",
        "intermediate_steps": [_agent_tool_step(plan, "table_0")],
    }

    turn2 = _resume_turn2(plan, "table_0", fake)
    resumed = turn2["plan"]
    geography = resumed.resolved_geography_intent()

    mock_agent_cls.assert_called_once_with(mode="planning")
    _, kwargs = mock_agent_cls.return_value.solve.call_args
    assert kwargs["clarification_context"] is not None
    assert kwargs["clarification_context"].original_query == pending.original_query
    assert turn2["logs"][0] == "agent_clarification_resume: completed clarification turn"

    assert resumed.requires_clarification is False
    assert resumed.pending_geography_clarification is None
    assert geography is not None
    assert geography.geo_for == {"county": "*"}
    assert geography.geo_in == {"state": "06"}
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"
    assert ("geography", ("acs/acs5", 2023)) in fake.calls


@patch("src.workflows.agent_clarification_resume.CensusQueryAgent")
def test_row3_two_turn_chroma_shaped_table_then_geography(mock_agent_cls):
    fake = ChromaShapedRow3Retrieval()
    turn1 = geography_node(_turn1_state(), {}, dependencies=fake.dependencies())
    plan = turn1["plan"]
    pending = plan.pending_geography_clarification

    mock_agent_cls.return_value.offline_mode = False
    mock_agent_cls.return_value.solve.return_value = {
        "reasoning_trace": "Clarification tool steps: 1 (select_clarification_option)",
        "data_summary": "User selected table_2 (SEX BY AGE).",
        "answer_text": "Proceeding with B01001 for total population by age and sex.",
        "intermediate_steps": [_agent_tool_step(plan, "table_2")],
    }

    assert plan.requires_clarification is True
    assert pending is not None
    assert pending.requested_slot == "table"
    assert pending.reason_code == "TABLE_AMBIGUOUS"
    assert [option.candidate_id for option in pending.options] == [
        "table:acs/acs5:B25008",
        "table:acs/acs5:B25033",
        "table:acs/acs5:B01001",
    ]
    assert ("geography", ("acs/acs5", 2023)) not in fake.calls

    turn2 = _resume_turn2(plan, "table_2", fake)
    resumed = turn2["plan"]
    geography = resumed.resolved_geography_intent()

    mock_agent_cls.assert_called_once_with(mode="planning")
    assert turn2["logs"][0] == "agent_clarification_resume: completed clarification turn"

    assert resumed.requires_clarification is False
    assert geography is not None
    assert geography.geo_for == {"county": "*"}
    assert geography.geo_in == {"state": "06"}
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"
    assert ("geography", ("acs/acs5", 2023)) in fake.calls


def test_legacy_geography_resume_fallback_still_resolves_table_pick():
    fake = AmbiguousTablesFake()
    turn1 = geography_node(_turn1_state(), {}, dependencies=fake.dependencies())
    plan = turn1["plan"]

    turn2 = _resume_turn2(plan, "table_0", fake, use_agent_path=False)
    resumed = turn2["plan"]
    geography = resumed.resolved_geography_intent()

    assert resumed.requires_clarification is False
    assert geography is not None
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"
