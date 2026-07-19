"""Pytest defaults for runtime modernization and golden URL collection."""

from __future__ import annotations

import csv

import pytest

from app_test_scripts.census_url_fixtures import (
    RowResult,
    UrlAttempt,
    golden_dated_stem,
    write_json_artifact,
)

TIER3_RESULTS: list[RowResult] = []


@pytest.fixture(autouse=True)
def _modern_runtime_for_offline_tests(monkeypatch: pytest.MonkeyPatch):
    """Offline tests run against the modern create_agent runtime."""
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)


@pytest.fixture
def url_attempt_recorder() -> list[UrlAttempt]:
    return []


@pytest.fixture
def record_census_urls(url_attempt_recorder: list[UrlAttempt], monkeypatch: pytest.MonkeyPatch):
    import src.clients.census_api_utils as api_utils

    original = api_utils.fetch_census_data_typed

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.success is not None:
            url_attempt_recorder.append(
                UrlAttempt(
                    url=result.success.url,
                    success=True,
                    source="fetch_census_data_typed",
                    attempt_index=len(url_attempt_recorder),
                )
            )
        elif result.failure is not None:
            url_attempt_recorder.append(
                UrlAttempt(
                    url=result.failure.url or "",
                    success=False,
                    source="fetch_census_data_typed",
                    attempt_index=len(url_attempt_recorder),
                    error=result.failure.error_message,
                )
            )
        return result

    monkeypatch.setattr(api_utils, "fetch_census_data_typed", wrapper)
    return url_attempt_recorder


@pytest.fixture
def tier3_results_collector() -> list[RowResult]:
    return TIER3_RESULTS


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    if not TIER3_RESULTS:
        return

    json_path = golden_dated_stem("tier3_e2e").with_suffix(".json")
    csv_path = golden_dated_stem("tier3_e2e").with_suffix(".csv")
    payload = [row.to_dict() for row in TIER3_RESULTS]
    write_json_artifact(json_path, payload)

    fieldnames = [
        "row_no",
        "question",
        "composite",
        "failure_class",
        "url_verdict",
        "delivery_verdict",
        "api_call_count",
        "retry_recovered",
        "expected_url",
        "winning_url",
        "best_mismatch",
        "stopped_before_agent",
        "answer_preview",
        "suggested_fix_area",
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in TIER3_RESULTS:
            writer.writerow(row.to_dict())
