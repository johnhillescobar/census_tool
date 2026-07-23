"""Tier 3: natural-language E2E collection with URL capture and dual verdicts."""

from __future__ import annotations

import os
import uuid

import pytest

from app import create_census_graph
from app_test_scripts.census_url_fixtures import (
    build_row_result,
    golden_collect_mode,
    golden_strict_mode,
    load_golden_questions,
    parse_census_url,
)
from src.services.graph_session import build_fresh_thread_state, runnable_config

requires_credentials = pytest.mark.skipif(
    not os.getenv("CENSUS_API_KEY") or not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY and CENSUS_API_KEY",
)

FULL_124_MODE = os.getenv("CENSUS_GOLDEN_FULL_124", "").strip().lower() in {"1", "true", "yes"}
SMOKE_FAMILIES = {
    "national": 1,
    "state": 2,
    "county": 3,
    "place": 5,
    "zcta": 7,
    "groups_catalog": 9,
    "variables_catalog": 10,
    "cbsa": 11,
    "metropolitan_division": 12,
    "combined_statistical_area": 13,
    "new_england_area": 14,
    "urban_area": 15,
    "state_part": 17,
    "tract": 19,
    "block_group": 20,
    "county_subdivision": 22,
    "tribal_parent": 23,
    "puma": 24,
    "congressional_district": 25,
    "state_legislative_upper": 26,
    "state_legislative_lower": 27,
    "school_district": 34,
    "multiyear": 51,
    "region": 71,
    "division": 73,
    "subminor_civil_division": 76,
    "place_remainder": 77,
    "overlap_part": 80,
    "consolidated_city": 81,
    "alaska_native_corporation": 83,
    "aiannh": 84,
    "tribal_subdivision": 85,
    "reservation_entity": 86,
    "off_reservation_trust_land": 87,
    "tribal_census_tract": 88,
    "tribal_block_group": 89,
    "aiannh_part": 93,
    "reservation_entity_part": 94,
    "off_reservation_trust_land_part": 95,
    "tribal_census_tract_part": 96,
    "tribal_block_group_part": 98,
    "principal_city": 100,
    "cbsa_part": 104,
    "metropolitan_division_part": 106,
    "combined_statistical_area_part": 110,
    "place_part": 82,
    "elementary_school_district": 121,
    "secondary_school_district": 122,
    "national_wildcard": 123,
    "specific_puma": 124,
}
ALL_GOLDEN_ROWS = load_golden_questions()
SELECTED_ROW_NOS = {row.row_no for row in ALL_GOLDEN_ROWS} if FULL_124_MODE else set(SMOKE_FAMILIES.values())
SELECTED_ROWS = [row for row in ALL_GOLDEN_ROWS if row.row_no in SELECTED_ROW_NOS]


def test_stratified_smoke_rows_cover_every_golden_geography_family_and_catalog():
    all_data_families = {parse_census_url(row.expected_url).geo_for[0][0] for row in ALL_GOLDEN_ROWS if not row.is_catalog_url}
    smoke_rows = [row for row in ALL_GOLDEN_ROWS if row.row_no in set(SMOKE_FAMILIES.values())]
    smoke_data_families = {parse_census_url(row.expected_url).geo_for[0][0] for row in smoke_rows if not row.is_catalog_url}
    assert smoke_data_families == all_data_families
    assert {parse_census_url(row.expected_url).catalog_path for row in smoke_rows if row.is_catalog_url} == {
        "groups.json",
        "variables.json",
    }


@pytest.mark.integration
@pytest.mark.slow
@requires_credentials
@pytest.mark.parametrize("row", SELECTED_ROWS, ids=lambda r: f"row_{r.row_no}")
def test_nl_question_collect_url_and_delivery(row, record_census_urls, tier3_results_collector):
    if row.is_catalog_url:
        pytest.skip("Catalog queries may use a different agent tool path in Phase A")

    graph = create_census_graph()
    config = runnable_config(
        user_id="golden-url-e2e",
        thread_id=str(uuid.uuid4()),
    )
    final_state = graph.invoke(build_fresh_thread_state(row.question), config=config)

    row_result = build_row_result(row, record_census_urls, final_state)
    tier3_results_collector.append(row_result)

    if golden_collect_mode():
        return

    if golden_strict_mode():
        assert row_result.composite != "false_failure", row_result.to_dict()
        return

    # Default after baseline: only hard-fail false_failure (retries/extra calls allowed).
    assert row_result.composite != "false_failure", row_result.to_dict()
