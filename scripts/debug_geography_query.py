"""Run one Census graph query while printing node-level debug evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_test_scripts.census_url_fixtures import load_golden_questions
from config import (
    CHROMA_CATALOG_INDEX_VERSION,
    CHROMA_CATALOG_SCHEMA_VERSION,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
    LATEST_AVAILABLE_YEAR,
)


def _configure_chroma_env() -> None:
    load_dotenv()
    # Chroma collections built with OpenAIEmbeddingFunction expect this env var name.
    os.environ.setdefault("CHROMA_OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--question")
    source.add_argument("--golden-row", type=int)
    parser.add_argument("--stop-after", help="Stop after this LangGraph node emits an update")
    parser.add_argument("--thread-id", default="vscode-geography-debug")
    parser.add_argument("--show-candidates", action="store_true")
    parser.add_argument(
        "--inspect-tables",
        action="store_true",
        help="Inspect census_tables Chroma health and row parsing before running the graph",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Run table inspection and exit without executing the LangGraph workflow",
    )
    parser.add_argument(
        "--table-query",
        help="Override table search text used for Chroma inspection (default: analyzer output)",
    )
    parser.add_argument(
        "--planning-year",
        type=int,
        default=None,
        help=f"Year filter for table retrieval inspection (default: {LATEST_AVAILABLE_YEAR})",
    )
    parser.add_argument(
        "--peek-limit",
        type=int,
        default=5,
        help="Number of stored table rows to sample with collection.peek()",
    )
    return parser.parse_args()


def _question_from_args(args: argparse.Namespace) -> str | None:
    if args.question:
        return args.question
    if args.golden_row is None:
        return None
    row = next((item for item in load_golden_questions() if item.row_no == args.golden_row), None)
    if row is None:
        raise SystemExit(f"Golden row {args.golden_row} does not exist")
    return row.question


def _resolve_table_query(question: str | None, override: str | None) -> str:
    if override:
        return override.strip()
    if not question:
        raise SystemExit("--table-query is required when no --question or --golden-row is provided")
    from src.services.census_retrieval_analyzer import analyze_retrieval_request

    return analyze_retrieval_request(question).table_search_text


def _compact(value: Any, *, show_candidates: bool) -> Any:
    if not isinstance(value, dict):
        return value
    payload = dict(value)
    if not show_candidates:
        payload.pop("candidates", None)
    return payload


def _score_from_distance(distance: object) -> float | None:
    if not isinstance(distance, int | float):
        return None
    return min(1.0, max(0.0, 1.0 - float(distance)))


def _years_available(raw: object, fallback: object) -> list[int]:
    if isinstance(raw, list):
        return [int(item) for item in raw if isinstance(item, int | str | float)]
    if isinstance(raw, str):
        return [int(item) for item in raw.split(",") if item.strip()]
    if fallback in (None, ""):
        return []
    if isinstance(fallback, int | str | float):
        return [int(fallback)]
    return []


def _try_parse_table_row(doc_id: str, metadata: dict[str, Any], distance: object) -> tuple[str, Any]:
    """Mirror _candidate_from_metadata table parsing without importing private helpers."""
    from src.domain.geography_catalog import TableCandidate

    if metadata.get("candidate_id") != doc_id:
        raise ValueError(f"Chroma id and metadata candidate_id do not match ({doc_id!r} vs {metadata.get('candidate_id')!r})")
    display_name = (
        metadata.get("display_name")
        or metadata.get("table_name")
        or metadata.get("geography_hierarchy")
        or doc_id
    )
    return (
        "ok",
        TableCandidate(
            candidate_id=doc_id,
            dataset=metadata["dataset"],
            year=int(metadata["year"]),
            display_name=str(display_name),
            score=_score_from_distance(distance),
            provenance=metadata["provenance"],
            schema_version=metadata["schema_version"],
            table_code=metadata["table_code"],
            table_name=metadata["table_name"],
            category=metadata["category"],
            years_available=_years_available(metadata.get("years_available"), metadata.get("year")),
        ),
    )


def inspect_table_index(*, table_query: str, planning_year: int, peek_limit: int) -> None:
    """Print collection metadata, typed query status, and peek() row validation."""
    from src.clients.chroma_utils import initialize_chroma_client, query_table_collection
    from src.domain.geography_catalog import TableCandidate
    from src.services.chroma_catalog_retriever import retrieve_table_candidates

    print("\n=== census_tables inspection ===")
    print(f"table_query={table_query!r}")
    print(f"planning_year={planning_year}")

    chroma_client = initialize_chroma_client()
    if isinstance(chroma_client, dict):
        print(f"client_error={chroma_client.get('error')}")
        return

    try:
        collection = chroma_client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
    except Exception as exc:
        print(f"collection_error={exc!r}")
        return

    metadata = collection.metadata or {}
    print("\n[collection metadata]")
    print(f"path={CHROMA_PERSIST_DIRECTORY}")
    print(f"metadata={json.dumps(metadata, indent=2, default=str)}")
    print(f"document_count={collection.count()}")
    print(f"expected_schema_version={CHROMA_CATALOG_SCHEMA_VERSION}")
    print(f"expected_index_version={CHROMA_CATALOG_INDEX_VERSION}")
    schema_ok = metadata.get("schema_version") == CHROMA_CATALOG_SCHEMA_VERSION
    index_ok = metadata.get("index_version") == CHROMA_CATALOG_INDEX_VERSION
    print(f"schema_version_ok={schema_ok}")
    print(f"index_version_ok={index_ok}")

    raw_result = query_table_collection(chroma_client, table_query)
    print("\n[chroma query: parse + embed]")
    print(f"status={raw_result.status}")
    print(f"reason={raw_result.reason!r}")
    print(f"schema_version={raw_result.schema_version!r}")
    print(f"index_version={raw_result.index_version!r}")
    print(f"candidate_ids={raw_result.candidate_ids}")
    if raw_result.candidates:
        for candidate in raw_result.candidates[:3]:
            print(
                f"  candidate={candidate.candidate_id} "
                f"table={candidate.table_code} years={candidate.years_available}"
            )

    grounded = retrieve_table_candidates(table_query, year=planning_year, client=chroma_client)
    print("\n[grounded table retrieval: app path with year filter]")
    print(f"status={grounded.status}")
    print(f"schema_version={grounded.schema_version!r}")
    print(f"index_version={grounded.index_version!r}")
    print(f"candidate_ids={grounded.candidate_ids}")
    if grounded.candidates:
        for candidate in grounded.candidates[:3]:
            if isinstance(candidate, TableCandidate):
                print(
                    f"  candidate={candidate.candidate_id} "
                    f"table={candidate.table_code} years={candidate.years_available}"
                )

    print(f"\n[peek sample limit={peek_limit}]")
    sample = collection.peek(limit=max(1, peek_limit))
    ids = sample.get("ids") or []
    metadatas = sample.get("metadatas") or []
    distances = sample.get("distances") or [None] * len(ids)
    if not ids:
        print("no documents returned by peek()")
        return

    for index, doc_id in enumerate(ids):
        raw_meta = metadatas[index] if index < len(metadatas) else {}
        meta = cast(dict[str, Any], dict(raw_meta))
        distance = distances[index] if index < len(distances) else None
        print(f"\n--- row {index + 1} ---")
        print(f"chroma_id={doc_id!r}")
        print(f"metadata={json.dumps(meta, indent=2, default=str)}")
        print(f"id_matches_candidate_id={doc_id == meta.get('candidate_id')}")
        print(f"year={meta.get('year')!r}")
        print(f"years_available={meta.get('years_available')!r}")
        try:
            status, parsed = _try_parse_table_row(doc_id, meta, distance)
            print(f"parse_status={status}")
            print(f"parsed_table={parsed.table_code} dataset={parsed.dataset} years={parsed.years_available}")
        except Exception as exc:
            print("parse_status=fail")
            print(f"parse_error={type(exc).__name__}: {exc}")


def _run_graph(question: str, args: argparse.Namespace, checkpoint: Path) -> None:
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


def main() -> None:
    _configure_chroma_env()
    args = _arguments()
    question = _question_from_args(args)
    planning_year = args.planning_year or LATEST_AVAILABLE_YEAR

    if args.inspect_only and not args.inspect_tables:
        args.inspect_tables = True

    if not args.inspect_only and question is None:
        raise SystemExit("Provide --question or --golden-row to run the graph workflow")

    if args.inspect_tables:
        table_query = _resolve_table_query(question, args.table_query)
        inspect_table_index(
            table_query=table_query,
            planning_year=planning_year,
            peek_limit=args.peek_limit,
        )
        if args.inspect_only:
            return

    if question is None:
        raise SystemExit("Provide --question or --golden-row to run the graph workflow")

    checkpoint = Path(tempfile.gettempdir()) / f"census-debug-{os.getpid()}.db"
    os.environ["CENSUS_CHECKPOINT_DB"] = str(checkpoint)
    os.environ.setdefault("CENSUS_TELEMETRY_STRICT", "1")
    _run_graph(question, args, checkpoint)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
