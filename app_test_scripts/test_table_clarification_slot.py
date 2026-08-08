"""Table-slot clarification must not reuse geography wording or geo_* option ids."""

from __future__ import annotations

from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.domain.clarification_templates import (
    normalize_geography_reason,
    normalize_table_reason,
    render_slot_clarification,
)
from src.domain.geography_catalog import CatalogCandidate, TableCandidate
from src.domain.geography_contract import ClarificationOption
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis
from src.services.graph_session import build_fresh_thread_state
from src.workflows.geography import geography_node
from src.workflows.temporal import temporal_node


class AmbiguousTablesFake(FakeGroundedRetrieval):
    """Close scores, neither label exact-matches table_search_text → stay ambiguous."""

    def retrieve_tables(self, analysis: CensusRetrievalAnalysis, *, year: int) -> RetrievalEvidence:
        self.calls.append(("table", year))
        candidates: list[CatalogCandidate] = [
            TableCandidate(
                candidate_id="table:acs/acs5:B01001",
                dataset="acs/acs5",
                year=year,
                display_name="SEX BY AGE",
                score=0.54,
                provenance="census_groups",
                schema_version="1.0",
                table_code="B01001",
                table_name="SEX BY AGE",
                category="detail",
                years_available=[year],
            ),
            TableCandidate(
                candidate_id="table:acs/acs5:B01002",
                dataset="acs/acs5",
                year=year,
                display_name="MEDIAN AGE BY SEX",
                score=0.53,
                provenance="census_groups",
                schema_version="1.0",
                table_code="B01002",
                table_name="MEDIAN AGE BY SEX",
                category="detail",
                years_available=[year],
            ),
        ]
        return RetrievalEvidence(
            evidence_id="table-evidence",
            collection_name="census_tables",
            status="hit",
            query_text=analysis.table_search_text,
            index_version="1.0",
            schema_version="1.0",
            candidate_ids=[candidate.candidate_id for candidate in candidates],
            candidates=candidates,
        )


def test_normalize_table_reason_keeps_table_ambiguous_out_of_geography_bucket():
    assert normalize_table_reason("CANDIDATE_AMBIGUOUS") == "TABLE_AMBIGUOUS"
    assert normalize_table_reason("TABLE_SCHEMA_MISMATCH") == "TABLE_SCHEMA_MISMATCH"
    assert normalize_geography_reason("CANDIDATE_AMBIGUOUS") == "GEOGRAPHY_AMBIGUOUS"


def test_render_slot_clarification_uses_table_copy_for_table_slot():
    prompt = render_slot_clarification(
        "CANDIDATE_AMBIGUOUS",
        [ClarificationOption(option_id="table_0", label="TOTAL POPULATION")],
        requested_slot="table",
    )
    assert prompt.reason_code == "TABLE_AMBIGUOUS"
    assert prompt.template_id == "table.ambiguous.v1"
    assert "tables" in prompt.question_text.casefold()
    assert "geography records" not in prompt.question_text.casefold()


def test_ambiguous_table_selection_offers_table_options_not_geography_copy():
    fake = AmbiguousTablesFake()
    state = build_fresh_thread_state("Show total population for all California counties in 2023.")
    temporal = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal["plan"]})
    result = geography_node(state, {}, dependencies=fake.dependencies())
    plan = result["plan"]
    pending = plan.pending_geography_clarification
    final = result["final"]

    assert plan.requires_clarification is True
    assert pending is not None
    assert pending.requested_slot == "table"
    assert pending.reason_code == "TABLE_AMBIGUOUS"
    assert plan.geography.reason_code == "TABLE_AMBIGUOUS"
    assert final["reason_code"] == "TABLE_AMBIGUOUS"
    assert [option.option_id for option in pending.options] == ["table_0", "table_1"]
    assert pending.options[0].label == "SEX BY AGE"
    assert final["clarification_type"] == "table"
    assert "Census tables" in final["answer_text"]
    assert "geography records" not in final["answer_text"].casefold()
    assert final["answer_text"].startswith("I found multiple Census tables")
