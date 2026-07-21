"""Run one Census graph query while printing node-level debug evidence."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app_test_scripts.census_url_fixtures import load_golden_questions


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--question")
    source.add_argument("--golden-row", type=int)
    parser.add_argument("--stop-after", help="Stop after this LangGraph node emits an update")
    parser.add_argument("--thread-id", default="vscode-geography-debug")
    parser.add_argument("--show-candidates", action="store_true")
    return parser.parse_args()


def _question_from_args(args: argparse.Namespace) -> str:
    if args.question:
        return args.question
    row = next((item for item in load_golden_questions() if item.row_no == args.golden_row), None)
    if row is None:
        raise SystemExit(f"Golden row {args.golden_row} does not exist")
    return row.question


def _compact(value: Any, *, show_candidates: bool) -> Any:
    if not isinstance(value, dict):
        return value
    payload = dict(value)
    if not show_candidates:
        payload.pop("candidates", None)
    return payload


def main() -> None:
    args = _arguments()
    question = _question_from_args(args)
    checkpoint = Path(tempfile.gettempdir()) / f"census-debug-{os.getpid()}.db"
    os.environ["CENSUS_CHECKPOINT_DB"] = str(checkpoint)
    os.environ.setdefault("CENSUS_TELEMETRY_STRICT", "1")

    from app import create_census_graph
    from src.services.graph_session import build_fresh_thread_state, runnable_config

    graph = create_census_graph()
    config = runnable_config(user_id="vscode-debug", thread_id=args.thread_id)
    state = build_fresh_thread_state(question)

    print(f"question={question!r}")
    print(f"checkpoint={checkpoint}")
    for update in graph.stream(state, config=config, stream_mode="updates"):
        for node, patch in update.items():
            print(f"\n[{node}]")
            print(json.dumps(_compact(patch, show_candidates=args.show_candidates), indent=2, default=str))
            if node == args.stop_after:
                return


if __name__ == "__main__":
    main()
