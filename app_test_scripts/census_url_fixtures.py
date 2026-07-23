"""Golden Census URL fixtures, parsing, comparison, and Tier 3 row verdicts."""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from src.workflows.output import is_census_data_renderable

GOLDEN_CSV = Path(__file__).resolve().parents[1] / "test_questions" / "test_questions_new.csv"
GOLDEN_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "migration_evidence" / "golden_urls"

CATALOG_SUFFIXES = ("/groups.json", "/variables.json")
IGNORABLE_EXTRA_VARS = frozenset({"GEO_ID"})

FAILURE_PHRASES = ("unable to complete",)

COMPOSITE_PRIORITY = {
    "false_failure": 0,
    "blocked": 1,
    "true_failure": 2,
    "pass_with_warnings": 3,
    "pass": 4,
}


@dataclass(frozen=True)
class GoldenQuestionRow:
    row_no: int
    source_label: str
    question: str
    expected_url: str

    @property
    def is_catalog_url(self) -> bool:
        return self.expected_url.rstrip("/").endswith(CATALOG_SUFFIXES)


@dataclass(frozen=True)
class CensusUrlParts:
    year: int | None
    dataset: str | None
    get_vars: tuple[str, ...]
    geo_for: tuple[tuple[str, str], ...]
    geo_in: tuple[tuple[str, str], ...]
    catalog_path: str | None = None


@dataclass(frozen=True)
class GoldenGeographyPlan:
    """Canonical geography expectation parsed from a golden Census URL."""

    geo_for: tuple[tuple[str, str], ...]
    geo_in: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class UrlCompareResult:
    equivalent: bool
    mismatches: tuple[str, ...] = ()


@dataclass
class UrlAttempt:
    url: str
    success: bool
    source: str = "fetch_census_data_typed"
    attempt_index: int = 0
    error: str | None = None
    url_equivalent_to_golden: bool | None = None


@dataclass
class RowResult:
    row_no: int
    question: str
    expected_url: str
    source_label: str = ""
    url_attempts: list[UrlAttempt] = field(default_factory=list)
    failed_attempt_count: int = 0
    successful_attempt_count: int = 0
    retry_recovered: bool = False
    winning_url: str | None = None
    url_verdict: str = "fail"
    delivery_verdict: str = "fail"
    composite: str = "true_failure"
    failure_class: str = "unknown"
    stopped_before_agent: bool = False
    requires_clarification: bool = False
    final_census_success: bool = False
    answer_has_failure_phrase: bool = False
    answer_preview: str = ""
    best_mismatch: str = ""
    api_call_count: int = 0
    suggested_fix_area: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["url_attempts"] = [asdict(a) for a in self.url_attempts]
        return payload


def golden_collect_mode() -> bool:
    return os.getenv("CENSUS_GOLDEN_COLLECT", "").strip() in {"1", "true", "yes"}


def golden_strict_mode() -> bool:
    return os.getenv("CENSUS_GOLDEN_STRICT", "").strip() in {"1", "true", "yes"}


def golden_artifacts_dir() -> Path:
    GOLDEN_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return GOLDEN_ARTIFACTS_DIR


def golden_dated_stem(prefix: str) -> Path:
    return golden_artifacts_dir() / f"{prefix}_{date.today().strftime('%Y%m%d')}"


def load_golden_questions(csv_path: Path = GOLDEN_CSV) -> list[GoldenQuestionRow]:
    rows: list[GoldenQuestionRow] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            rows.append(
                GoldenQuestionRow(
                    row_no=int(raw["No"]),
                    source_label=raw["Question with source"].strip(),
                    question=raw["Question friendly human"].strip(),
                    expected_url=raw["API call"].strip(),
                )
            )
    return rows


_GEO_PAIR_PATTERN = re.compile(r"(?P<level>.+?):(?P<value>[^\s]*)(?:\s+|$)")


def _split_geo_clause(clause: str) -> tuple[tuple[str, str], ...]:
    clause = unquote(clause).strip()
    if not clause:
        return ()
    return tuple(
        (match.group("level").strip().lower(), match.group("value").strip()) for match in _GEO_PAIR_PATTERN.finditer(clause)
    )


def _data_path_parts(path: str) -> tuple[int | None, str | None]:
    """Return (year, dataset) from a /data/{year}/{dataset...} Census API path."""
    parts = path.split("/")
    if len(parts) < 4 or parts[1] != "data":
        return None, None
    year_token = parts[2]
    year = int(year_token) if year_token.isdigit() else None
    dataset = "/".join(parts[3:]) if len(parts) > 3 else None
    return year, dataset


def parse_census_url(url: str) -> CensusUrlParts:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")

    for suffix in CATALOG_SUFFIXES:
        if path.endswith(suffix):
            parts = path.split("/")
            year_token = parts[2] if len(parts) > 2 else ""
            year = int(year_token) if year_token.isdigit() else None
            dataset = "/".join(parts[3:-1]) if len(parts) > 4 else None
            return CensusUrlParts(
                year=year,
                dataset=dataset,
                get_vars=(),
                geo_for=(),
                geo_in=(),
                catalog_path=parts[-1],
            )

    year, dataset = _data_path_parts(path)

    qs = parse_qs(parsed.query, keep_blank_values=True)
    get_raw = qs.get("get", [""])[0]
    get_vars = tuple(sorted(v.strip().upper() for v in get_raw.split(",") if v.strip()))
    geo_for = _split_geo_clause(qs.get("for", [""])[0])
    geo_in = _split_geo_clause(qs.get("in", [""])[0])

    return CensusUrlParts(
        year=year,
        dataset=dataset,
        get_vars=get_vars,
        geo_for=geo_for,
        geo_in=geo_in,
        catalog_path=None,
    )


def geography_plan_from_url(url: str) -> GoldenGeographyPlan | None:
    """Return the canonical geography oracle for a data URL."""
    parts = parse_census_url(url)
    if parts.catalog_path is not None:
        return None
    return GoldenGeographyPlan(geo_for=parts.geo_for, geo_in=parts.geo_in)


def strip_api_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = "&".join(piece for piece in parsed.query.split("&") if not piece.startswith("key="))
    return parsed._replace(query=kept).geturl()


def normalize_for_compare(url: str) -> CensusUrlParts:
    return parse_census_url(strip_api_key_from_url(url))


def _group_prefix(variable: str) -> str | None:
    upper = variable.upper()
    if upper.startswith("GROUP(") and upper.endswith(")"):
        return upper[6:-1]
    return None


def _is_allowed_extra_var(variable: str) -> bool:
    return variable == "NAME" or variable in IGNORABLE_EXTRA_VARS


def variables_compatible(expected: tuple[str, ...], actual: tuple[str, ...]) -> bool:
    if expected == actual:
        return True

    exp_set = set(expected)
    act_set = set(actual)
    if exp_set.issubset(act_set):
        return True

    exp_groups = {p for p in (_group_prefix(v) for v in expected) if p is not None}
    act_groups = {p for p in (_group_prefix(v) for v in actual) if p is not None}

    if exp_groups and not act_groups:
        prefix = next(iter(exp_groups))
        return all(_is_allowed_extra_var(v) or v.startswith(prefix) for v in actual)
    if act_groups and not exp_groups:
        prefix = next(iter(act_groups))
        return all(_is_allowed_extra_var(v) or v.startswith(prefix) for v in expected)

    return False


def compare_census_urls(expected: str, actual: str) -> UrlCompareResult:
    exp = normalize_for_compare(expected)
    act = normalize_for_compare(actual)
    mismatches: list[str] = []

    if exp.catalog_path or act.catalog_path:
        ok = exp.year == act.year and exp.dataset == act.dataset and exp.catalog_path == act.catalog_path
        return UrlCompareResult(ok, () if ok else ("catalog path mismatch",))

    if exp.year != act.year:
        mismatches.append(f"year: expected {exp.year}, got {act.year}")
    if exp.dataset != act.dataset:
        mismatches.append(f"dataset: expected {exp.dataset!r}, got {act.dataset!r}")
    if exp.geo_for != act.geo_for:
        mismatches.append(f"for: expected {exp.geo_for}, got {act.geo_for}")
    if exp.geo_in != act.geo_in:
        mismatches.append(f"in: expected {exp.geo_in}, got {act.geo_in}")
    if not variables_compatible(exp.get_vars, act.get_vars):
        mismatches.append(f"get: expected {exp.get_vars}, got {act.get_vars}")

    return UrlCompareResult(not mismatches, tuple(mismatches))


def rebuild_url_from_golden(expected_url: str) -> str:
    """Rebuild a golden data URL via build_census_url using raw query clauses."""
    from src.clients.census_api_utils import build_census_url

    parts = parse_census_url(expected_url)
    if parts.catalog_path:
        raise ValueError("catalog URLs are not rebuilt")

    parsed = urlparse(expected_url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    get_raw = qs.get("get", [""])[0]
    if get_raw.upper().startswith("GROUP("):
        variables = [get_raw]
    else:
        variables = [v.strip() for v in get_raw.split(",") if v.strip()]

    filters: dict[str, str] = {}
    if "for" in qs:
        filters["for"] = qs["for"][0]
    if "in" in qs:
        filters["in"] = qs["in"][0]

    assert parts.year is not None
    assert parts.dataset is not None
    rebuilt = build_census_url(
        dataset=parts.dataset,
        year=parts.year,
        variables=variables,
        geo={"filters": filters},
    )
    return strip_api_key_from_url(rebuilt)


def _delivery_verdict(final_state: dict[str, Any], *, expect_clarification: bool = False) -> str:
    plan = final_state.get("plan")
    final = final_state.get("final") or {}
    artifacts = final_state.get("artifacts") or {}
    census = artifacts.get("census_data") or {}

    requires_clarification = bool(getattr(plan, "requires_clarification", False) if plan else False)
    if expect_clarification:
        return "pass" if requires_clarification else "fail"

    if requires_clarification:
        return "clarification"

    answer = (final.get("answer_text") or "").lower()
    if any(phrase in answer for phrase in FAILURE_PHRASES):
        return "fail"

    if isinstance(census, dict) and census.get("success") is True:
        if is_census_data_renderable(census):
            return "pass"
        if (final.get("answer_text") or "").strip():
            return "pass_with_warnings"

    if (final.get("answer_text") or "").strip():
        return "pass_with_warnings"

    return "fail"


def _composite(url_verdict: str, delivery_verdict: str) -> str:
    if url_verdict == "pass" and delivery_verdict in {"pass", "pass_with_warnings"}:
        return "pass"
    if url_verdict == "pass" and delivery_verdict in {"fail", "clarification"}:
        return "false_failure"
    if url_verdict == "fail" and delivery_verdict in {"pass", "pass_with_warnings"}:
        return "pass_with_warnings"
    if url_verdict == "fail" and delivery_verdict == "clarification":
        return "blocked"
    return "true_failure"


def classify_failure(row_result: RowResult) -> str:
    if row_result.composite == "false_failure":
        if row_result.answer_has_failure_phrase:
            return "false_failure_parser"
        return "false_failure_artifact_wiring"

    if row_result.composite == "blocked":
        if row_result.stopped_before_agent:
            return "geography_blocked"
        return "clarification_resume_missing"

    if row_result.composite == "pass_with_warnings" and row_result.url_verdict == "fail":
        if row_result.successful_attempt_count == 0:
            return "agent_wrong_url"
        return "multi_call_partial"

    if row_result.composite == "true_failure":
        if row_result.api_call_count == 0 and row_result.requires_clarification:
            return "geography_blocked"
        if row_result.api_call_count == 0:
            return "agent_no_calls"
        return "agent_wrong_url"

    return "none"


def _suggested_fix_area(failure_class: str) -> str:
    mapping = {
        "geography_blocked": "src/workflows/geography.py",
        "clarification_resume_missing": "src/services/graph_session.py",
        "false_failure_parser": "src/agents/census_query_agent.py",
        "false_failure_plan_validator": "src/services/plan_result_validator.py",
        "false_failure_artifact_wiring": "src/workflows/agent.py",
        "tier1_builder_drift": "src/clients/census_api_utils.py",
        "tier2_stale_fixture": "test_questions/test_questions_new.csv",
        "agent_wrong_url": "src/agents/census_query_agent.py",
        "agent_no_calls": "src/workflows/geography.py",
        "multi_call_partial": "src/domain/execution_spec.py",
        "none": "",
    }
    return mapping.get(failure_class, "")


def build_row_result(
    row: GoldenQuestionRow,
    url_attempts: list[UrlAttempt],
    final_state: dict[str, Any],
    *,
    expect_clarification: bool = False,
) -> RowResult:
    for idx, attempt in enumerate(url_attempts):
        attempt.attempt_index = idx
        if row.is_catalog_url:
            attempt.url_equivalent_to_golden = False
        else:
            attempt.url_equivalent_to_golden = compare_census_urls(row.expected_url, attempt.url).equivalent

    successful = [a for a in url_attempts if a.success]
    failed = [a for a in url_attempts if not a.success]
    equivalent_successes = [a for a in successful if a.url_equivalent_to_golden]

    if row.is_catalog_url:
        url_verdict = "not_applicable"
    elif equivalent_successes:
        url_verdict = "pass"
    else:
        url_verdict = "fail"

    delivery = _delivery_verdict(final_state, expect_clarification=expect_clarification)
    composite = _composite(url_verdict, delivery) if not row.is_catalog_url else "not_applicable"

    plan = final_state.get("plan")
    final = final_state.get("final") or {}
    artifacts = final_state.get("artifacts") or {}
    census = artifacts.get("census_data") or {}
    logs = final_state.get("logs") or []
    answer_text = final.get("answer_text") or ""

    stopped_before_agent = any(
        isinstance(entry, str)
        and entry.startswith(("geography:", "temporal:", "benchmark:", "comparison:"))
        and "clarification required" in entry
        for entry in logs
    ) and not any(isinstance(entry, str) and entry.startswith("agent:") and "skipped" not in entry for entry in logs)

    best_mismatch = ""
    if successful and not equivalent_successes and not row.is_catalog_url:
        comparisons = [compare_census_urls(row.expected_url, a.url) for a in successful]
        if comparisons:
            best_mismatch = "; ".join(comparisons[0].mismatches)

    result = RowResult(
        row_no=row.row_no,
        question=row.question,
        expected_url=row.expected_url,
        source_label=row.source_label,
        url_attempts=url_attempts,
        failed_attempt_count=len(failed),
        successful_attempt_count=len(successful),
        retry_recovered=bool(failed and equivalent_successes),
        winning_url=equivalent_successes[-1].url if equivalent_successes else (successful[-1].url if successful else None),
        url_verdict=url_verdict,
        delivery_verdict=delivery,
        composite=composite,
        stopped_before_agent=stopped_before_agent,
        requires_clarification=bool(getattr(plan, "requires_clarification", False) if plan else False),
        final_census_success=isinstance(census, dict) and census.get("success") is True,
        answer_has_failure_phrase=any(p in answer_text.lower() for p in FAILURE_PHRASES),
        answer_preview=answer_text[:200],
        best_mismatch=best_mismatch,
        api_call_count=len(url_attempts),
    )
    result.failure_class = classify_failure(result)
    result.suggested_fix_area = _suggested_fix_area(result.failure_class)
    return result


def write_json_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_tier1_record(
    records: list[dict[str, Any]],
    row: GoldenQuestionRow,
    *,
    rebuilt_url: str | None,
    result: UrlCompareResult,
) -> None:
    records.append(
        {
            "row_no": row.row_no,
            "question": row.question,
            "expected_url": row.expected_url,
            "rebuilt_url": rebuilt_url,
            "equivalent": result.equivalent,
            "mismatches": list(result.mismatches),
            "failure_class": "catalog_special_case"
            if row.is_catalog_url
            else ("none" if result.equivalent else "tier1_builder_drift"),
        }
    )
