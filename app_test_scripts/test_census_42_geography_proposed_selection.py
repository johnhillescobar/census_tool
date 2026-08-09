"""CENSUS-42 increment 2 — geography_node uses proposed-ID validation, not score-rank."""

from __future__ import annotations

from unittest.mock import MagicMock

from app_test_scripts.grounded_planning_fakes import FakeGroundedRetrieval
from src.domain.retrieval_plan import GroundedSelection
from src.services.census_retrieval_analyzer import analyze_retrieval_request
from src.services.graph_session import build_fresh_thread_state
from src.services.grounded_plan_validator import validate_grounded_plan
from src.workflows.geography import GroundedGeographyDependencies, geography_node
from src.workflows.temporal import temporal_node


def _production_deps(fake: FakeGroundedRetrieval, *, select: MagicMock | None = None) -> GroundedGeographyDependencies:
    tracker = select if select is not None else MagicMock()
    return GroundedGeographyDependencies(
        analyze=fake.analyze,
        retrieve_tables=fake.retrieve_tables,
        retrieve_geographies=fake.retrieve_geographies,
        select=tracker,
        validate=validate_grounded_plan,
    )


def _full_proposal() -> GroundedSelection:
    return GroundedSelection(
        selection_id="selection:test",
        status="selected",
        evidence_ids=["table-evidence", "hierarchy-evidence", "area-evidence"],
        selected_table_ids=["table:population"],
        selected_hierarchy_id="hierarchy:county",
        selected_area_ids=["area:california"],
    )


def test_geography_node_validates_proposed_selection_without_score_rank():
    fake = FakeGroundedRetrieval()
    score_rank = MagicMock()
    deps = _production_deps(fake, select=score_rank)

    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    plan = temporal_result["plan"].model_copy(update={"proposed_selection": _full_proposal()})
    state = state.model_copy(update={"plan": plan})

    result = geography_node(state, {}, dependencies=deps)

    score_rank.assert_not_called()
    assert result["plan"].grounded_plan is not None
    assert result["plan"].requires_clarification is False
    assert result["plan"].selected_table is not None
    assert result["plan"].selected_table.table_code == "B01003"


def test_geography_node_clarifies_when_no_proposal_in_production_path():
    fake = FakeGroundedRetrieval()
    deps = GroundedGeographyDependencies(
        analyze=fake.analyze,
        retrieve_tables=fake.retrieve_tables,
        retrieve_geographies=fake.retrieve_geographies,
        select=None,
        validate=validate_grounded_plan,
    )

    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})

    result = geography_node(state, {}, dependencies=deps)

    assert result["plan"].requires_clarification is True
    assert result["plan"].pending_geography_clarification is not None
    assert result["plan"].pending_geography_clarification.requested_slot == "table"
    assert result["plan"].pending_geography_clarification.reason_code == "TABLE_NOT_FOUND"
    assert result["plan"].grounded_plan is None


def test_harness_fake_still_uses_score_rank_when_no_proposal():
    fake = FakeGroundedRetrieval()
    state = build_fresh_thread_state("Show total population for all California counties in 2023")
    temporal_result = temporal_node(state, {})
    state = state.model_copy(update={"plan": temporal_result["plan"]})

    result = geography_node(state, {}, dependencies=fake.dependencies())

    assert result["plan"].grounded_plan is not None
    assert result["plan"].requires_clarification is False


def test_geography_node_reuses_attached_retrieval_evidence_without_re_retrieving():
    fake = FakeGroundedRetrieval()
    deps = GroundedGeographyDependencies(
        analyze=fake.analyze,
        retrieve_tables=fake.retrieve_tables,
        retrieve_geographies=fake.retrieve_geographies,
        select=None,
        validate=validate_grounded_plan,
    )

    question = "Show total population for all California counties in 2023"
    analysis = analyze_retrieval_request(question)
    table_evidence = fake.retrieve_tables(analysis, year=2023)
    geography_evidence = fake.retrieve_geographies(analysis, dataset="acs/acs5", year=2023)
    fake.calls.clear()

    state = build_fresh_thread_state(question)
    temporal_result = temporal_node(state, {})
    plan = temporal_result["plan"].model_copy(
        update={
            "retrieval_evidence": [table_evidence, *geography_evidence.evidence],
            "proposed_selection": _full_proposal(),
        }
    )
    state = state.model_copy(update={"plan": plan})

    result = geography_node(state, {}, dependencies=deps)

    assert fake.calls == [("analyze", question)]
    assert result["plan"].grounded_plan is not None
    assert result["plan"].requires_clarification is False
