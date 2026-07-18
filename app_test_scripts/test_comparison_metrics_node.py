from src.domain.comparison_artifacts import ComparisonInputRow, ComparisonMetricArtifactRow
from src.domain.comparison_plan import ComparisonPlan
from src.state.types import CensusState
from src.workflows.comparison_metrics import comparison_metrics_node


def _build_plan_dict() -> dict:
    return ComparisonPlan(
        query_years=[2020],
        dataset="acs/acs5",
        metric="population",
        subject_geo_level="county",
        subject_geos=["10001", "10002"],
        benchmark_geo_level="county",
        benchmark_geos=["10001", "10002"],
        comparison_op="difference",
        normalization="none",
        missing_year_policy="skip_with_note",
        derived_metrics=["difference"],
        join_keys=["year", "geo_id"],
        requested_text="compare counties",
    ).model_dump()


def _build_rows() -> list[dict]:
    return [
        ComparisonInputRow(
            year=2020,
            geo_id="10001",
            metric="population",
            value=100.0,
            benchmark_value=90.0,
        ).model_dump(),
        ComparisonInputRow(
            year=2020,
            geo_id="10002",
            metric="population",
            value=80.0,
            benchmark_value=90.0,
        ).model_dump(),
    ]


def test_comparison_metrics_node_computes_metrics_for_valid_state():
    state = CensusState(
        plan={"requires_clarification": False, "comparison": _build_plan_dict()},
        artifacts={"comparison_input_rows": _build_rows()},
    )

    result = comparison_metrics_node(state, config={})

    assert "comparison_metrics: computed 2 rows" in result["logs"][0]
    metrics = result["artifacts"]["comparison_metrics"]
    assert len(metrics) == 2
    validated = [ComparisonMetricArtifactRow.model_validate(row) for row in metrics]
    assert validated[0].derived_metric == "difference"


def test_comparison_metrics_node_skips_without_rows():
    state = CensusState(
        plan={"requires_clarification": False, "comparison": _build_plan_dict()},
        artifacts={},
    )

    result = comparison_metrics_node(state, config={})

    assert result["logs"] == ["comparison_metrics: skipped (no comparison input rows)"]
    assert "comparison_metrics" not in result.get("artifacts", {})


def test_comparison_metrics_node_fail_closed_on_invalid_rows():
    state = CensusState(
        plan={"requires_clarification": False, "comparison": _build_plan_dict()},
        artifacts={
            "comparison_input_rows": [
                {
                    "year": 2020,
                    "geo_id": "10001",
                    "metric": "population",
                    "value": 100.0,
                    "benchmark_value": 90.0,
                    "unexpected": True,
                }
            ]
        },
    )

    result = comparison_metrics_node(state, config={})

    assert result["logs"] == ["comparison_metrics: failed (invalid comparison rows)"]
    assert "invalid rows" in result["error"]


def test_comparison_metrics_node_skips_on_clarification_gate():
    state = CensusState(
        plan={"requires_clarification": True, "comparison": _build_plan_dict()},
        artifacts={"comparison_input_rows": _build_rows()},
    )

    result = comparison_metrics_node(state, config={})

    assert result["logs"] == ["comparison_metrics: skipped (clarification required)"]
