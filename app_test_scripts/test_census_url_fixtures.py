"""Unit tests for golden URL fixture helpers."""

from __future__ import annotations

import pytest

from app_test_scripts.census_url_fixtures import (
    UrlAttempt,
    build_row_result,
    compare_census_urls,
    geography_plan_from_url,
    load_golden_questions,
    normalize_for_compare,
    parse_census_url,
    rebuild_url_from_golden,
    variables_compatible,
)


def test_load_golden_questions_has_124_rows():
    rows = load_golden_questions()
    assert len(rows) == 124
    assert rows[2].row_no == 3
    assert "California counties" in rows[2].question


def test_parse_row3_county_california_url():
    row = load_golden_questions()[2]
    parts = parse_census_url(row.expected_url)
    assert parts.year == 2023
    assert parts.dataset == "acs/acs5"
    assert ("county", "*") in parts.geo_for
    assert ("state", "06") in parts.geo_in
    assert "B01001_001E" in parts.get_vars


@pytest.mark.parametrize(
    ("row_no", "expected_for", "expected_in"),
    [
        (7, (("zip code tabulation area", "60601"),), ()),
        (11, (("metropolitan statistical area/micropolitan statistical area", ""),), ()),
        (
            17,
            (("state (or part)", "*"),),
            (("metropolitan statistical area/micropolitan statistical area", "35620"),),
        ),
        (
            20,
            (("block group", "*"),),
            (("state", "36"), ("county", "061"), ("tract", "003100")),
        ),
        (
            23,
            (("tract", "*"),),
            (("american indian area/alaska native area/hawaiian home land", "2430"),),
        ),
        (
            80,
            (("county (or part)", "*"),),
            (("state", "06"), ("place", "44000")),
        ),
        (
            98,
            (("tribal block group (or part)", "*"),),
            (
                (
                    "american indian area/alaska native area (reservation or statistical entity only)",
                    "2555R",
                ),
                ("tribal census tract (or part)", "T00500"),
            ),
        ),
        (
            103,
            (("county", "*"),),
            (
                ("metropolitan statistical area/micropolitan statistical area", "31080"),
                ("metropolitan division", "31084"),
                ("state (or part)", "06"),
            ),
        ),
        (120, (("zip code tabulation area", "*"),), ()),
    ],
)
def test_golden_geography_plan_oracle(
    row_no: int,
    expected_for: tuple[tuple[str, str], ...],
    expected_in: tuple[tuple[str, str], ...],
):
    row = next(row for row in load_golden_questions() if row.row_no == row_no)
    plan = geography_plan_from_url(row.expected_url)
    assert plan is not None
    assert plan.geo_for == expected_for
    assert plan.geo_in == expected_in


def test_parse_catalog_url():
    row = load_golden_questions()[8]
    parts = parse_census_url(row.expected_url)
    assert parts.catalog_path == "groups.json"
    assert parts.year == 2023


def test_normalize_strips_api_key():
    url = (
        "https://api.census.gov/data/2023/acs/acs5?"
        "get=NAME,B01001_001E&for=county:*&in=state:06&key=secret"
    )
    parts = normalize_for_compare(url)
    assert parts.geo_in == (("state", "06"),)


def test_variables_compatible_group_vs_individual():
    expected = ("NAME", "GROUP(B17001)")
    actual = ("NAME", "B17001_001E", "B17001_002E")
    assert variables_compatible(expected, actual)


def test_variables_compatible_group_expansion_allows_geo_id():
    expected = ("NAME", "GROUP(B17001)")
    actual = ("NAME", "GEO_ID", "B17001_001E", "B17001_002E")
    assert variables_compatible(expected, actual)


def test_compare_equivalent_urls_with_geo_id_superset():
    expected = "https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=county:*&in=state:06"
    actual = "https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID,B01001_001E&for=county:*&in=state:06"
    assert compare_census_urls(expected, actual).equivalent


def test_rebuild_row3_matches_golden():
    row = load_golden_questions()[2]
    rebuilt = rebuild_url_from_golden(row.expected_url)
    assert compare_census_urls(row.expected_url, rebuilt).equivalent


def test_build_row_result_false_failure_detection():
    row = load_golden_questions()[2]
    attempts = [
        UrlAttempt(
            url=row.expected_url,
            success=True,
            url_equivalent_to_golden=True,
        )
    ]
    final_state = {
        "plan": None,
        "final": {"answer_text": "I was unable to complete this query."},
        "artifacts": {"census_data": {"success": False, "data": []}},
        "logs": ["agent: plan context attached"],
    }
    result = build_row_result(row, attempts, final_state)
    assert result.url_verdict == "pass"
    assert result.composite == "false_failure"
    assert result.failure_class == "false_failure_parser"


def test_build_row_result_blocked_geography():
    row = load_golden_questions()[2]
    final_state = {
        "plan": type("Plan", (), {"requires_clarification": True})(),
        "final": {"answer_text": "Which geography should I use?"},
        "artifacts": {},
        "logs": ["geography: clarification required (GEOGRAPHY_AMBIGUOUS)"],
    }
    result = build_row_result(row, [], final_state)
    assert result.composite == "blocked"
    assert result.failure_class == "geography_blocked"


def test_tier3_backlog_rows_exclude_passing_rows():
    from app_test_scripts.export_golden_url_report import tier3_backlog_rows

    tier3 = [
        {"row_no": 1, "question": "passing", "composite": "pass", "failure_class": "none"},
        {"row_no": 2, "question": "blocked", "composite": "blocked", "failure_class": "geography_blocked"},
    ]
    backlog = tier3_backlog_rows(tier3)
    assert [row["row_no"] for row in backlog] == [2]
