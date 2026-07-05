from unittest.mock import patch

from src.domain.comparison_artifacts import ComparisonInputRow
from src.domain.comparison_plan import ComparisonPlan
from src.state.types import CensusState
from src.workflows.agent import agent_reasoning_node


def _build_comparison_plan_dict() -> dict:
    return ComparisonPlan(
        query_years=[2020],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["10001", "10002", "10003"],
        benchmark_geo_level="county",
        benchmark_geos=["10001", "10002", "10003"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare counties",
    ).model_dump()


def _build_state(*, with_comparison_plan: bool) -> CensusState:
    plan = {"requires_clarification": False}
    if with_comparison_plan:
        plan["comparison"] = _build_comparison_plan_dict()

    return CensusState(
        messages=[{"role": "user", "content": "Compare county population"}],
        plan=plan,
    )


def _mock_agent_result() -> dict:
    return {
        "census_data": {
            "success": True,
            "url": "https://api.census.gov/data/2020/acs/acs5",
            "data": [
                ["geo_id", "year", "B01003_001E"],
                ["10001", "2020", "100"],
                ["10002", "2020", "80"],
                ["10003", "2020", "60"],
            ],
        },
        "data_summary": "County population comparison for 2020",
        "reasoning_trace": "Fetched county population data",
        "answer_text": "County population comparison complete.",
        "charts_needed": [],
        "tables_needed": [],
        "footnotes": ["Source: U.S. Census Bureau"],
    }


@patch("src.workflows.agent.CensusQueryAgent")
def test_agent_emits_comparison_input_rows_when_plan_present(mock_agent_cls):
    mock_agent_cls.return_value.solve.return_value = _mock_agent_result()

    result = agent_reasoning_node(_build_state(with_comparison_plan=True), config={})

    rows = result["artifacts"]["comparison_input_rows"]
    assert len(rows) == 3
    validated_rows = [ComparisonInputRow.model_validate(row) for row in rows]
    assert validated_rows[0].metric == "population"


@patch("src.workflows.agent.CensusQueryAgent")
def test_agent_does_not_emit_comparison_input_rows_without_plan(mock_agent_cls):
    mock_agent_cls.return_value.solve.return_value = _mock_agent_result()

    result = agent_reasoning_node(_build_state(with_comparison_plan=False), config={})

    assert "comparison_input_rows" not in result["artifacts"]


def test_agent_skips_when_clarification_required():
    state = CensusState(
        messages=[{"role": "user", "content": "Compare population"}],
        plan={"requires_clarification": True},
    )

    result = agent_reasoning_node(state, config={})

    assert result["logs"] == ["agent: skipped (clarification required)"]
    assert "artifacts" not in result
