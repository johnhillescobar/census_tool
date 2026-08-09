"""Table-slot resume must continue geography planning after a grounded table pick."""

from __future__ import annotations

from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from app_test_scripts.test_table_clarification_slot import AmbiguousTablesFake
from src.domain.geography_catalog import TableCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis
from src.services.graph_session import build_fresh_thread_state
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


def test_table_resume_resolves_geography_after_ambiguous_table_pick():
    fake = AmbiguousTablesFake()
    turn1 = geography_node(_turn1_state(), {}, dependencies=fake.dependencies())
    plan = turn1["plan"]
    pending = plan.pending_geography_clarification
    assert pending is not None
    assert pending.requested_slot == "table"

    resume_state = _turn1_state().model_copy(update={"plan": plan, "messages": [{"role": "user", "content": "table_0"}]})
    turn2 = geography_resume_node(resume_state, {"configurable": {"grounded_geography_dependencies": fake.dependencies()}})
    resumed = turn2["plan"]
    geography = resumed.resolved_geography_intent()

    assert resumed.requires_clarification is False
    assert resumed.pending_geography_clarification is None
    assert geography is not None
    assert geography.geo_for == {"county": "*"}
    assert geography.geo_in == {"state": "06"}
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"
    assert ("geography", ("acs/acs5", 2023)) in fake.calls


def test_row3_two_turn_chroma_shaped_table_then_geography():
    fake = ChromaShapedRow3Retrieval()
    turn1 = geography_node(_turn1_state(), {}, dependencies=fake.dependencies())
    plan = turn1["plan"]
    pending = plan.pending_geography_clarification

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

    resume_state = _turn1_state().model_copy(update={"plan": plan, "messages": [{"role": "user", "content": "table_2"}]})
    turn2 = geography_resume_node(resume_state, {"configurable": {"grounded_geography_dependencies": fake.dependencies()}})
    resumed = turn2["plan"]
    geography = resumed.resolved_geography_intent()

    assert resumed.requires_clarification is False
    assert geography is not None
    assert geography.geo_for == {"county": "*"}
    assert geography.geo_in == {"state": "06"}
    assert resumed.selected_table is not None
    assert resumed.selected_table.table_code == "B01001"
    assert ("geography", ("acs/acs5", 2023)) in fake.calls
