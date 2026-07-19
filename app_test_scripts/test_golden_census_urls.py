"""Tier 1: offline golden URL parse and rebuild contract tests."""

from __future__ import annotations

import pytest

from app_test_scripts.census_url_fixtures import (
    append_tier1_record,
    compare_census_urls,
    golden_collect_mode,
    golden_dated_stem,
    load_golden_questions,
    parse_census_url,
    rebuild_url_from_golden,
    write_json_artifact,
)

GOLDEN_ROWS = load_golden_questions()
TIER1_RECORDS: list[dict] = []


@pytest.fixture(scope="session", autouse=True)
def _no_census_api_key_in_rebuild_urls():
    """Rebuild comparisons must not embed CENSUS_API_KEY into committed artifacts."""
    import os

    prior = os.environ.pop("CENSUS_API_KEY", None)
    yield
    if prior is not None:
        os.environ["CENSUS_API_KEY"] = prior


@pytest.fixture(scope="session", autouse=True)
def _write_tier1_baseline():
    yield
    write_json_artifact(golden_dated_stem("tier1_baseline").with_suffix(".json"), TIER1_RECORDS)


@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: f"row_{r.row_no}")
def test_golden_url_parses(row):
    parts = parse_census_url(row.expected_url)
    if row.is_catalog_url:
        assert parts.catalog_path is not None
        append_tier1_record(
            TIER1_RECORDS,
            row,
            rebuilt_url=None,
            result=compare_census_urls(row.expected_url, row.expected_url),
        )
        return

    assert parts.year is not None
    assert parts.dataset
    assert parts.get_vars


@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: f"row_{r.row_no}")
def test_golden_url_rebuilds(row):
    if row.is_catalog_url:
        pytest.skip("catalog URLs are not rebuilt")

    rebuilt = rebuild_url_from_golden(row.expected_url)
    result = compare_census_urls(row.expected_url, rebuilt)
    append_tier1_record(TIER1_RECORDS, row, rebuilt_url=rebuilt, result=result)

    if golden_collect_mode():
        return

    assert result.equivalent, result.mismatches
