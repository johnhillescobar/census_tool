"""Tier 2: direct HTTP smoke tests for golden Census URLs."""

from __future__ import annotations

import os

import pytest
import requests

from app_test_scripts.census_url_fixtures import (
    golden_dated_stem,
    load_golden_questions,
    write_json_artifact,
)

requires_census_key = pytest.mark.skipif(
    not os.getenv("CENSUS_API_KEY"),
    reason="Requires CENSUS_API_KEY for golden URL smoke tests",
)

GOLDEN_ROWS = load_golden_questions()
TIER2_RECORDS: list[dict] = []


@pytest.fixture(scope="session", autouse=True)
def _write_tier2_baseline():
    yield
    write_json_artifact(golden_dated_stem("tier2_smoke").with_suffix(".json"), TIER2_RECORDS)


@pytest.mark.integration
@requires_census_key
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: f"row_{r.row_no}")
def test_golden_url_smoke(row):
    url = row.expected_url
    api_key = os.getenv("CENSUS_API_KEY")
    if api_key and "key=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={api_key}"

    record = {
        "row_no": row.row_no,
        "question": row.question,
        "expected_url": row.expected_url,
        "http_status": None,
        "row_count": 0,
        "error": None,
        "failure_class": "none",
    }

    try:
        response = requests.get(url, timeout=60)
        record["http_status"] = response.status_code
        if response.status_code != 200:
            record["error"] = response.text[:500]
            record["failure_class"] = "stale_fixture"
        else:
            payload = response.json()
            if isinstance(payload, list):
                record["row_count"] = max(len(payload) - 1, 0)
            elif isinstance(payload, dict):
                record["row_count"] = len(payload)
            if record["row_count"] == 0 and not row.is_catalog_url:
                record["failure_class"] = "stale_fixture"
    except requests.RequestException as exc:
        record["error"] = str(exc)
        record["failure_class"] = "api_down"

    TIER2_RECORDS.append(record)
    assert record["http_status"] == 200, record.get("error")
    assert record["failure_class"] == "none", record
