import pytest
from pydantic import ValidationError

from src.domain.comparison_artifacts import (
    ComparisonCensusObservation,
    ComparisonInputRow,
    ComparisonInputRowBuildRequest,
    ComparisonInputRowsArtifact,
    ComparisonMetricArtifactRow,
    ComparisonMetricsArtifact,
)
from src.domain.comparison_plan import ComparisonPlan


def _build_plan() -> ComparisonPlan:
    return ComparisonPlan(
        query_years=[2020, 2021],
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
        requested_text="compare population",
    )


def test_comparison_input_row_valid_payload():
    row = ComparisonInputRow(
        year=2020,
        geo_id="10001",
        metric="population",
        value=100.0,
        benchmark_value=90.0,
    )
    assert row.model_dump() == {
        "year": 2020,
        "geo_id": "10001",
        "metric": "population",
        "value": 100.0,
        "benchmark_value": 90.0,
    }


def test_comparison_input_row_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ComparisonInputRow.model_validate(
            {
                "year": 2020,
                "geo_id": "10001",
                "metric": "population",
                "value": 100.0,
                "benchmark_value": 90.0,
                "unexpected": True,
            }
        )


def test_comparison_census_observation_requires_required_fields():
    with pytest.raises(ValidationError):
        ComparisonCensusObservation.model_validate(
            {
                "year": 2020,
                "geo_id": "10001",
                "metric": "population",
            }
        )


def test_comparison_input_row_build_request_validates_nested_models():
    request = ComparisonInputRowBuildRequest(
        plan=_build_plan(),
        observations=[
            ComparisonCensusObservation(
                year=2020,
                geo_id="10001",
                metric="population",
                value=100.0,
            )
        ],
    )
    assert request.plan.metric == "population"
    assert len(request.observations) == 1


def test_comparison_input_rows_artifact_rejects_extra_fields():
    row = ComparisonInputRow(
        year=2020,
        geo_id="10001",
        metric="population",
        value=100.0,
        benchmark_value=90.0,
    )
    artifact = ComparisonInputRowsArtifact(rows=[row])
    assert len(artifact.rows) == 1

    with pytest.raises(ValidationError):
        ComparisonInputRowsArtifact.model_validate({"rows": [row.model_dump()], "extra": 1})


def test_comparison_metrics_artifact_validates_output_rows():
    artifact = ComparisonMetricsArtifact(
        rows=[
            ComparisonMetricArtifactRow(
                year=2020,
                geo_id="10001",
                metric="population",
                derived_metric="difference",
                value=10.0,
                subject_value=100.0,
                benchmark_value=90.0,
                success=True,
            )
        ]
    )
    assert artifact.rows[0].derived_metric == "difference"
