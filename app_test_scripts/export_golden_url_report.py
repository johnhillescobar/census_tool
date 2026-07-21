"""Merge Tier 1-3 golden URL artifacts into summary and backlog CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_test_scripts.census_url_fixtures import COMPOSITE_PRIORITY  # noqa: E402

ARTIFACTS_DIR = PROJECT_ROOT / "migration_evidence" / "golden_urls"


def _latest(prefix: str) -> Path | None:
    matches = sorted(ARTIFACTS_DIR.glob(f"{prefix}_*.json"))
    return matches[-1] if matches else None


def _priority_for(composite: str, failure_class: str) -> str:
    if composite == "false_failure":
        return "P0"
    if failure_class == "geography_blocked":
        return "P0"
    if composite == "blocked":
        return "P1"
    if composite == "true_failure":
        return "P1"
    if composite == "pass_with_warnings":
        return "P2"
    return "P3"


def _component_for(failure_class: str) -> str:
    mapping = {
        "geography_blocked": "grounded geography retrieval",
        "clarification_resume_missing": "graph_session",
        "false_failure_parser": "census_query_agent",
        "false_failure_plan_validator": "plan_result_validator",
        "false_failure_artifact_wiring": "agent_workflow",
        "tier1_builder_drift": "census_api_utils",
        "tier2_stale_fixture": "golden_csv",
        "agent_wrong_url": "agent",
        "agent_no_calls": "planning_gate",
        "multi_call_partial": "execution_spec",
        "none": "none",
    }
    return mapping.get(failure_class, failure_class)


def load_json(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def tier3_backlog_rows(tier3_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in tier3_rows:
        composite = item.get("composite", "unknown")
        failure_class = item.get("failure_class", "unknown")
        if composite == "pass" or failure_class == "none":
            continue
        rows.append(
            {
                "row_no": item.get("row_no"),
                "question": item.get("question"),
                "composite": composite,
                "failure_class": failure_class,
                "priority": _priority_for(composite, failure_class),
                "component": _component_for(failure_class),
                "url_verdict": item.get("url_verdict"),
                "delivery_verdict": item.get("delivery_verdict"),
                "api_call_count": item.get("api_call_count"),
                "retry_recovered": item.get("retry_recovered"),
                "expected_url": item.get("expected_url"),
                "winning_url": item.get("winning_url"),
                "best_mismatch": item.get("best_mismatch"),
                "stopped_before_agent": item.get("stopped_before_agent"),
                "answer_preview": item.get("answer_preview"),
                "suggested_fix_area": item.get("suggested_fix_area"),
            }
        )

    rows.sort(
        key=lambda row: (
            COMPOSITE_PRIORITY.get(str(row["composite"]), 99),
            row.get("row_no") or 0,
        )
    )
    return rows


def write_summary(path: Path, *, tier1: list[dict], tier2: list[dict], tier3: list[dict], backlog: list[dict]) -> None:
    tier1_fail = sum(1 for row in tier1 if not row.get("equivalent"))
    tier2_fail = sum(1 for row in tier2 if row.get("failure_class") != "none")
    tier3_counts = Counter(row.get("composite", "unknown") for row in tier3)
    failure_counts = Counter(row.get("failure_class", "unknown") for row in tier3)

    lines = [
        f"# Golden URL Summary ({date.today().isoformat()})",
        "",
        "## Tier 1 — offline rebuild",
        f"- rows: {len(tier1)}",
        f"- rebuild mismatches: {tier1_fail}",
        "",
        "## Tier 2 — HTTP smoke",
        f"- rows: {len(tier2)}",
        f"- failures: {tier2_fail}",
        "",
        "## Tier 3 — NL E2E smoke",
        f"- rows: {len(tier3)}",
    ]
    for composite, count in sorted(tier3_counts.items(), key=lambda item: COMPOSITE_PRIORITY.get(item[0], 99)):
        lines.append(f"- {composite}: {count}")

    lines.extend(["", "## Tier 3 failure_class counts"])
    for failure_class, count in failure_counts.most_common():
        lines.append(f"- {failure_class}: {count}")

    lines.extend(["", "## Backlog rows", f"- total: {len(backlog)}", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export golden URL validation report")
    parser.add_argument("--date-stem", default=date.today().strftime("%Y%m%d"))
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    tier1 = load_json(_latest("tier1_baseline"))
    tier2 = load_json(_latest("tier2_smoke"))
    tier3 = load_json(_latest("tier3_e2e"))
    backlog = tier3_backlog_rows(tier3)

    backlog_path = ARTIFACTS_DIR / f"backlog_{args.date_stem}.csv"
    summary_path = ARTIFACTS_DIR / f"SUMMARY_{args.date_stem}.md"

    fieldnames = [
        "row_no",
        "question",
        "composite",
        "failure_class",
        "priority",
        "component",
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
    with backlog_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(backlog)

    write_summary(summary_path, tier1=tier1, tier2=tier2, tier3=tier3, backlog=backlog)
    print(f"Wrote {summary_path}")
    print(f"Wrote {backlog_path}")


if __name__ == "__main__":
    main()
