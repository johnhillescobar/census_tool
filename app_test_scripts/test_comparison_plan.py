from src.domain.comparison_plan import ComparisonPlan
import pytest

# Create tests for:


# valid canonical plan
def valid_payload() -> dict:
    return {
        "query_years": [2020, 2021, 2022],
        "dataset": "acs/acs5",
        "metric": "population",
        "subject_geo_level": "county",
        "subject_geos": ["10001", "10002", "10003"],
        "benchmark_geo_level": "county",
        "benchmark_geos": ["10001", "10002", "10003"],
        "comparison_op": "difference",
        "normalization": "none",
        "missing_year_policy": "skip_with_note",
        "derived_metrics": ["difference", "pct_difference"],
        "join_keys": ["year", "geo_id"],
        "requested_text": "compare population counties",
    }


def test_valid_canonical_plan():
    plan = ComparisonPlan(**valid_payload())
    assert plan.query_years == [2020, 2021, 2022]
    assert plan.dataset == "acs/acs5"


def test_empty_query_years():
    payload = valid_payload()
    payload["query_years"] = []
    with pytest.raises(ValueError, match="query_years must be non-empty"):
        ComparisonPlan(**payload)


# duplicate years
def test_duplicate_years():
    payload = valid_payload()
    payload["query_years"] = [2020, 2020, 2022]
    with pytest.raises(ValueError, match="query_years must be unique"):
        ComparisonPlan(**payload)


# empty derived_metrics
def test_empty_derived_metrics():
    payload = valid_payload()
    payload["derived_metrics"] = []
    with pytest.raises(ValueError, match="derived_metrics must be non-empty"):
        ComparisonPlan(**payload)


# empty join_keys
def test_empty_join_keys():
    payload = valid_payload()
    payload["join_keys"] = []
    with pytest.raises(ValueError, match="join_keys must be non-empty"):
        ComparisonPlan(**payload)


# empty subject_geos
def test_empty_subject_geos():
    payload = valid_payload()
    payload["subject_geos"] = []
    with pytest.raises(ValueError, match="subject_geos must be non-empty"):
        ComparisonPlan(**payload)
