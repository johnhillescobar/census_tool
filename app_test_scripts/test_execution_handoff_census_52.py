"""CENSUS-52: execution handoff for validated table-only grounded plans."""

from unittest.mock import patch

from src.domain.execution_spec import build_execution_spec
from src.domain.temporal_contract import TemporalIntent, TemporalResolved
from src.services.agent_plan_context import build_agent_plan_context, format_plan_directives
from src.services.grounded_execution_context import (
    GroundedExecutionContext,
    reset_grounded_execution_context,
    set_grounded_execution_context,
    validate_grounded_api_request,
)
from src.services.grounded_plan_validator import CanonicalTable, ValidatedGroundedPlan
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.agent import agent_reasoning_node


def _median_income_temporal() -> TemporalIntent:
    return TemporalIntent(
        mode="range",
        start_year=2015,
        end_year=2020,
        anchor_year=None,
        missing_year_policy="skip_with_note",
        requested_text="Show me median income trends from 2015 to 2020",
    )


def _table_only_grounded_plan() -> ValidatedGroundedPlan:
    return ValidatedGroundedPlan(
        selection_id="sel-table-only",
        evidence_ids=["tables"],
        table=CanonicalTable(
            candidate_id="table:acs/acs5:B19013",
            dataset="acs/acs5",
            year=2023,
            table_code="B19013",
            table_name="Median Household Income",
            category="detail",
            years_available=[2015, 2016, 2017, 2018, 2019, 2020],
        ),
        geography=None,
    )


def _table_only_workflow_plan() -> WorkflowPlan:
    grounded = _table_only_grounded_plan()
    return WorkflowPlan(
        temporal=TemporalResolved(time=_median_income_temporal()),
        selected_table=grounded.table,
        grounded_plan=grounded,
        requires_clarification=False,
    )


def test_build_agent_plan_context_table_only_grounded_plan():
    context = build_agent_plan_context(_table_only_workflow_plan())
    assert context is not None
    assert context.geography is None
    assert context.grounded_plan is not None
    assert context.grounded_plan.geography is None
    assert context.selected_table is not None
    assert context.selected_table.table_code == "B19013"


def test_format_plan_directives_table_only_include_table_years_and_national_default():
    context = build_agent_plan_context(_table_only_workflow_plan())
    assert context is not None
    directives = format_plan_directives(context)
    assert "Validated table: B19013" in directives
    assert "Required query years: [2015, 2016, 2017, 2018, 2019, 2020]" in directives
    assert "geo_for: {'us': '1'}" in directives
    assert "table-only (no geography evidence)" in directives
    assert "one Census API call per required year" in directives


def test_execution_spec_table_only_resolves_national_geography():
    context = build_agent_plan_context(_table_only_workflow_plan())
    assert context is not None
    spec = build_execution_spec(context)
    assert spec is not None
    assert spec.geography.geo_for == {"us": "1"}
    assert spec.query_years == [2015, 2016, 2017, 2018, 2019, 2020]
    assert spec.requires_time_series is True


def test_grounded_api_guard_accepts_table_only_national_request():
    plan = _table_only_grounded_plan()
    token = set_grounded_execution_context(
        GroundedExecutionContext(plan=plan, allowed_years=list(range(2015, 2021)))
    )
    try:
        accepted = validate_grounded_api_request(
            dataset=plan.table.dataset,
            year=2018,
            variables=["NAME", "B19013_001E"],
            geo_for={"us": "1"},
            geo_in={},
        )
        rejected = validate_grounded_api_request(
            dataset=plan.table.dataset,
            year=2018,
            variables=["NAME", "B19013_001E"],
            geo_for={"state": "06"},
            geo_in={},
        )
    finally:
        reset_grounded_execution_context(token)

    assert accepted is None
    assert rejected == "Table-only plan requires national geography geo_for={'us': '1'} with empty geo_in"


@patch("src.workflows.agent.CensusQueryAgent")
def test_agent_reasoning_node_passes_table_only_plan_context(mock_agent_cls):
    context = build_agent_plan_context(_table_only_workflow_plan())
    assert context is not None
    mock_agent = mock_agent_cls.return_value
    mock_agent.solve.return_value = {
        "census_data": {"success": True, "data": [["Year", "Median"], ["2015", "55000"]]},
        "data_summary": "US median income",
        "reasoning_trace": "Fetched ACS",
        "answer_text": "Median household income trend from 2015 to 2020.",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": ["Source: U.S. Census Bureau"],
    }

    state = CensusState(
        messages=[{"role": "user", "content": "Show me median income trends from 2015 to 2020"}],
        plan=_table_only_workflow_plan(),
    )
    result = agent_reasoning_node(state, config={})

    _, kwargs = mock_agent.solve.call_args
    passed = kwargs["plan_context"]
    assert passed is not None
    assert passed.geography is None
    assert passed.grounded_plan is not None
    assert passed.grounded_plan.table.table_code == "B19013"
    assert result["logs"][0] == "agent: plan context attached (table-only execution)"
