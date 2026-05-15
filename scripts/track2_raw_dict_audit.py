#!/usr/bin/env python3
"""
Track 2E heuristic drift scanner for ``dict[str, Any]`` / ``Dict[str, Any]`` text.

Usage:
    uv run python scripts/track2_raw_dict_audit.py
    uv run python scripts/track2_raw_dict_audit.py --summary
    uv run python scripts/track2_raw_dict_audit.py --strict --max-hits "$(Get-Content scripts/track2_raw_dict_baseline.txt)"

``--strict`` must be paired with ``--max-hits N`` where *N* matches
``scripts/track2_raw_dict_baseline.txt`` (unsuppressed hit count). The process
exits 1 only when new uncommented hits exceed *N*.

Tag intentional survivors on the offending line: ``track2-raw-dict-allow``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_TARGETS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "streamlit_app.py",
)
SKIP_DIR_NAMES = {"__pycache__", ".venv", ".mypy_cache", ".git", ".pytest_cache"}
SUPPRESSION_TOKEN = "track2-raw-dict-allow"
PATTERN = re.compile(r"\b(?:dict|Dict)\[\s*str\s*,\s*Any\s*\]")


def iter_py_files(base: Path) -> list[Path]:
    out: list[Path] = []
    if base.is_file():
        return [base]
    for path in sorted(base.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            path.relative_to(PROJECT_ROOT / "app_test_scripts")
        except ValueError:
            pass
        else:
            continue
        seg = path.relative_to(PROJECT_ROOT).as_posix()
        if seg.startswith("migration_evidence/"):
            continue
        out.append(path)
    return out


def scan(paths: tuple[Path, ...]) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for base in paths:
        if not base.exists():
            continue
        for py in iter_py_files(base):
            try:
                text = py.read_text(encoding="utf-8")
            except OSError:
                continue
            for lineno, raw_line in enumerate(text.splitlines(), start=1):
                if PATTERN.search(raw_line):
                    hits.append((py, lineno, raw_line.rstrip()))
    return hits


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Ratchet enforcement; requires ``--max-hits``.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print aggregate counts (no per-line listing).",
    )
    parser.add_argument(
        "--max-hits",
        type=int,
        default=None,
        help="Uncommented hit ceiling when used with ``--strict`` (ratchet).",
    )
    args = parser.parse_args(argv)

    hits = scan(SCAN_TARGETS)
    uncommented = [h for h in hits if SUPPRESSION_TOKEN not in h[2]]

    print(f"Track 2 raw dict pattern hits (all lines): {len(hits)}")
    print(
        f"Track 2 raw dict pattern hits (missing '{SUPPRESSION_TOKEN}'): "
        f"{len(uncommented)}"
    )

    if args.strict and args.max_hits is None:
        print("--strict requires --max-hits <baseline_integer>", file=sys.stderr)
        return 1

    if args.strict and len(uncommented) > args.max_hits:
        print(
            f"Strict ratchet: {len(uncommented)} uncommented hits > {args.max_hits}",
            file=sys.stderr,
        )
        return 1

    if not args.summary:
        for path, lineno, line in hits:
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            print(f"{rel}:{lineno}:{line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))