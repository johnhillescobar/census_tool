"""Build-time Census area enumeration for the geography areas Chroma index."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import chromadb
import requests
from chromadb.api import ClientAPI
from chromadb.config import Settings

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from config import (
    CATALOG_YEAR_START,
    CENSUS_API_TIMEOUT,
    CENSUS_CATALOG_INDEX_VERSION,
    CENSUS_CATALOG_SCHEMA_VERSION,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    LATEST_AVAILABLE_YEAR,
)
from index.build_geography_index import _create_embedding_function
from src.domain.geography_catalog import IndexManifest

load_dotenv()


LOGGER = logging.getLogger("geography_areas_index")
BASE_URL = "https://api.census.gov/data"
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PARTITION_FILE = WORKSPACE_ROOT / "index" / "partitions" / "us_state_fips.json"
DEFAULT_AREA_DATASET = "acs/acs5"

NATIONAL_LEVELS = (
    "us",
    "state",
    "zip code tabulation area",
    "metropolitan statistical area/micropolitan statistical area",
)
STATE_PARENT_LEVELS = (
    "county",
    "place",
    "congressional district",
    "public use microdata area",
    "school district (unified)",
    "state legislative district (upper chamber)",
    "state legislative district (lower chamber)",
)


class HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class HttpClient(Protocol):
    def get(self, url: str, *, params: dict[str, str], timeout: int) -> HttpResponse: ...


class RequestsHttpClient:
    def get(self, url: str, *, params: dict[str, str], timeout: int) -> requests.Response:
        return requests.get(url, params=params, timeout=timeout)


_DEFAULT_HTTP_CLIENT = RequestsHttpClient()


@dataclass(frozen=True)
class AreaPartition:
    """Parent clauses used to bound high-volume Census enumerations."""

    parents: tuple[tuple[str, str], ...] = ()

    @property
    def label(self) -> str:
        return " ".join(f"{level}:{value}" for level, value in self.parents) or "all"


@dataclass(frozen=True)
class AreaRow:
    name: str
    geo_id: str
    geography_code: str
    census_token: str
    dataset: str
    year: int
    partition: AreaPartition


@dataclass(frozen=True)
class AreaJob:
    dataset: str
    year: int
    census_token: str
    partition: AreaPartition = field(default_factory=AreaPartition)

    @property
    def key(self) -> str:
        return f"{self.dataset}|{self.year}|{self.census_token}|{self.partition.label}"

    @property
    def source_url(self) -> str:
        return f"{BASE_URL}/{self.year}/{self.dataset}"


def census_api_key() -> str | None:
    return os.getenv("CENSUS_API_KEY")


def require_census_api_key() -> str:
    key = census_api_key()
    if not key:
        raise ValueError("CENSUS_API_KEY is not set")
    return key


def parse_partition(value: str) -> AreaPartition:
    parents: list[tuple[str, str]] = []
    for clause in filter(None, (item.strip() for item in value.split(","))):
        if ":" not in clause:
            raise ValueError(f"partition clause must be LEVEL:VALUE: {clause!r}")
        level, code = clause.split(":", 1)
        if not level.strip() or not code.strip():
            raise ValueError(f"partition clause must have a level and value: {clause!r}")
        parents.append((level.strip(), code.strip()))
    return AreaPartition(tuple(parents))


def enumeration_params(census_token: str, partition: AreaPartition) -> dict[str, str]:
    params = {"get": "NAME,GEO_ID", "for": f"{census_token}:*"}
    if partition.parents:
        params["in"] = " ".join(f"{level}:{value}" for level, value in partition.parents)
    key = census_api_key()
    if key:
        params["key"] = key
    return params


def fetch_area_rows(
    dataset: str,
    year: int,
    census_token: str,
    partition: AreaPartition,
    *,
    http_client: HttpClient = _DEFAULT_HTTP_CLIENT,
) -> list[AreaRow]:
    require_census_api_key()
    url = f"{BASE_URL}/{year}/{dataset}"
    response = http_client.get(
        url,
        params=enumeration_params(census_token, partition),
        timeout=CENSUS_API_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise ValueError("Census area enumeration returned an invalid table")
    headers = [str(value) for value in payload[0]]
    required = {"NAME", "GEO_ID", census_token}
    missing = required.difference(headers)
    if missing:
        raise ValueError(f"Census area enumeration is missing columns: {sorted(missing)}")

    rows: list[AreaRow] = []
    for raw in payload[1:]:
        if not isinstance(raw, list) or len(raw) != len(headers):
            raise ValueError("Census area enumeration row width does not match headers")
        record = dict(zip(headers, (str(value) for value in raw)))
        rows.append(
            AreaRow(
                name=record["NAME"],
                geo_id=record["GEO_ID"],
                geography_code=record[census_token],
                census_token=census_token,
                dataset=dataset,
                year=year,
                partition=partition,
            )
        )
    return rows


def stable_area_id(row: AreaRow) -> str:
    canonical = "\x1f".join((row.dataset, str(row.year), row.census_token, row.geo_id))
    return f"geo-area:{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"


def area_document(row: AreaRow) -> str:
    aliases = ", ".join(area_aliases(row.name))
    return (
        f"Census area: {row.name}. Geography level: {row.census_token}. "
        f"Geography code: {row.geography_code}. Aliases: {aliases}."
    )


def area_aliases(name: str) -> list[str]:
    pieces = [piece.strip() for piece in name.split(",") if piece.strip()]
    return list(dict.fromkeys([name.strip(), *pieces]))


def area_metadata(row: AreaRow) -> dict[str, str | int]:
    candidate_id = stable_area_id(row)
    return {
        "candidate_id": candidate_id,
        "dataset": row.dataset,
        "year": row.year,
        "display_name": row.name,
        "census_token": row.census_token,
        "friendly_level": row.census_token.replace("(or part)", "").strip(),
        "geo_id": row.geo_id,
        "geography_code": row.geography_code,
        "parent_clauses": json.dumps(row.partition.parents),
        "partition": row.partition.label,
        "aliases": json.dumps(area_aliases(row.name)),
        "provenance": "census_api",
        "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
        "index_version": CENSUS_CATALOG_INDEX_VERSION,
    }


def load_partitions(values: Sequence[str], partition_file: Path | None) -> list[AreaPartition]:
    raw_values = list(values)
    if partition_file:
        payload = json.loads(partition_file.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise ValueError("partition file must contain a JSON list of LEVEL:VALUE strings")
        raw_values.extend(payload)
    return [parse_partition(value) for value in raw_values] or [AreaPartition()]


def iter_default_area_jobs(
    *,
    year_start: int,
    year_end: int,
    dataset: str = DEFAULT_AREA_DATASET,
    state_partition_file: Path | None = None,
) -> list[AreaJob]:
    """Option 2 default matrix: national + per-state levels (no tracts/BGs)."""
    if year_end < year_start:
        raise ValueError("year_end must be >= year_start")
    state_file = state_partition_file or DEFAULT_STATE_PARTITION_FILE
    state_partitions = load_partitions([], state_file)
    jobs: list[AreaJob] = []
    for year in range(year_start, year_end + 1):
        for level in NATIONAL_LEVELS:
            jobs.append(AreaJob(dataset=dataset, year=year, census_token=level, partition=AreaPartition()))
        for level in STATE_PARENT_LEVELS:
            for partition in state_partitions:
                jobs.append(AreaJob(dataset=dataset, year=year, census_token=level, partition=partition))
    return jobs


def county_child_jobs(
    county_rows: Sequence[AreaRow],
    *,
    include_tracts: bool,
    include_block_groups: bool,
) -> list[AreaJob]:
    """Expand successful county enumerations into opt-in tract/BG jobs."""
    jobs: list[AreaJob] = []
    if not include_tracts and not include_block_groups:
        return jobs
    levels: list[str] = []
    if include_tracts:
        levels.append("tract")
    if include_block_groups:
        levels.append("block group")
    seen: set[str] = set()
    for row in county_rows:
        state_code = next((code for level, code in row.partition.parents if level == "state"), None)
        if not state_code:
            continue
        partition = AreaPartition((("state", state_code), ("county", row.geography_code)))
        for level in levels:
            job = AreaJob(dataset=row.dataset, year=row.year, census_token=level, partition=partition)
            if job.key in seen:
                continue
            seen.add(job.key)
            jobs.append(job)
    return jobs


def ensure_areas_collection(
    client: ClientAPI,
    *,
    delete_existing: bool = True,
    embedding_function: object | None = None,
):
    embedder = cast(Any, embedding_function or _create_embedding_function())
    if delete_existing:
        try:
            client.get_collection(CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME)
            client.delete_collection(CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME)
            LOGGER.info("Deleted existing collection: %s", CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME)
        except Exception:
            LOGGER.info("No existing %s collection to delete", CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME)
        return client.create_collection(
            name=CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
            metadata={
                "description": "Official Census NAME,GEO_ID geography enumeration",
                "hnsw:space": "cosine",
                "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
                "index_version": CENSUS_CATALOG_INDEX_VERSION,
                "built_at": datetime.now(UTC).isoformat(),
            },
            embedding_function=embedder,
        )
    return client.get_or_create_collection(
        CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
        metadata={
            "description": "Official Census NAME,GEO_ID geography enumeration",
            "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
            "index_version": CENSUS_CATALOG_INDEX_VERSION,
        },
        embedding_function=embedder,
    )


def upsert_area_rows(
    client: ClientAPI,
    rows: Sequence[AreaRow],
    *,
    batch_size: int = 500,
    collection: Any | None = None,
    embedding_function: object | None = None,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    target = collection or ensure_areas_collection(
        client,
        delete_existing=False,
        embedding_function=embedding_function,
    )
    unique_rows = {stable_area_id(row): row for row in rows}
    ordered = [unique_rows[candidate_id] for candidate_id in sorted(unique_rows)]
    for start in range(0, len(ordered), batch_size):
        batch = ordered[start : start + batch_size]
        target.upsert(
            ids=[stable_area_id(row) for row in batch],
            documents=[area_document(row) for row in batch],
            metadatas=[area_metadata(row) for row in batch],
        )
    return len(ordered)


def write_area_manifest(
    path: Path,
    *,
    rows: Sequence[AreaRow],
    source_urls: Iterable[str],
) -> IndexManifest:
    unique_rows = {stable_area_id(row): row for row in rows}
    return write_cumulative_area_manifest(
        path,
        document_count=len(unique_rows),
        datasets=sorted({row.dataset for row in unique_rows.values()}),
        years=sorted({row.year for row in unique_rows.values()}),
        partitions=sorted({row.partition.label for row in unique_rows.values()}),
        source_urls=sorted(set(source_urls)),
    )


def write_cumulative_area_manifest(
    path: Path,
    *,
    document_count: int,
    datasets: Sequence[str],
    years: Sequence[int],
    partitions: Sequence[str],
    source_urls: Sequence[str],
) -> IndexManifest:
    manifest = IndexManifest(
        collection_name=CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
        schema_version=CENSUS_CATALOG_SCHEMA_VERSION,
        index_version=CENSUS_CATALOG_INDEX_VERSION,
        document_count=document_count,
        datasets=sorted(set(datasets)),
        years=sorted(set(years)),
        source_urls=sorted(set(source_urls)),
        partitions=sorted(set(partitions)),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def _empty_progress() -> dict[str, Any]:
    return {
        "completed": [],
        "failures": [],
        "datasets": [],
        "years": [],
        "partitions": [],
        "source_urls": [],
    }


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_progress()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        LOGGER.warning("progress file %s is empty; treating as fresh progress", path)
        return _empty_progress()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        LOGGER.warning(
            "progress file %s is invalid JSON (%s); treating as fresh progress",
            path,
            exc,
        )
        return _empty_progress()
    if not isinstance(payload, dict):
        raise ValueError("progress file must be a JSON object")
    progress = _empty_progress()
    for key in progress:
        value = payload.get(key, progress[key])
        if key == "failures":
            progress[key] = value if isinstance(value, list) else []
        elif key in {"years"}:
            progress[key] = [int(item) for item in value] if isinstance(value, list) else []
        else:
            progress[key] = [str(item) for item in value] if isinstance(value, list) else []
    return progress


def _write_json_resilient(path: Path, payload: object, *, retries: int = 8) -> None:
    """Write JSON with retries; Dropbox/Windows often denies os.replace on hot files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            LOGGER.warning(
                "atomic replace blocked (attempt %s/%s): %s -> %s (%s)",
                attempt,
                retries,
                tmp_path.name,
                path.name,
                exc,
            )
            time.sleep(min(0.05 * (2 ** (attempt - 1)), 2.0))
        except OSError as exc:
            last_error = exc
            LOGGER.warning(
                "atomic replace failed (attempt %s/%s): %s -> %s (%s)",
                attempt,
                retries,
                tmp_path.name,
                path.name,
                exc,
            )
            time.sleep(min(0.05 * (2 ** (attempt - 1)), 2.0))

    LOGGER.warning(
        "atomic replace exhausted for %s (%s); falling back to direct write",
        path,
        last_error,
    )
    try:
        path.write_text(text, encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    """Persist progress; prefer atomic replace, fall back if Windows locks the file."""
    _write_json_resilient(path, progress)


def write_failures_file(path: Path, failures: Sequence[dict[str, object]]) -> None:
    _write_json_resilient(path, list(failures))


def build_areas_index(
    persist_dir: str | Path,
    *,
    year_start: int = CATALOG_YEAR_START,
    year_end: int = LATEST_AVAILABLE_YEAR,
    delete_existing: bool = True,
    resume: bool = False,
    include_tracts: bool = False,
    include_block_groups: bool = False,
    batch_size: int = 500,
    dataset: str = DEFAULT_AREA_DATASET,
    state_partition_file: Path | None = None,
    progress_path: Path | None = None,
    failures_path: Path | None = None,
    manifest_path: Path | None = None,
    client: ClientAPI | None = None,
    embedding_function: object | None = None,
    http_client: HttpClient = _DEFAULT_HTTP_CLIENT,
    logger: logging.Logger | None = None,
) -> int:
    """Delete/recreate (unless resume) and fill census_geography_areas for Option 2 matrix."""
    log = logger or LOGGER
    require_census_api_key()
    persist = Path(persist_dir)
    persist.mkdir(parents=True, exist_ok=True)
    progress_file = progress_path or (persist / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.progress.json")
    failures_file = failures_path or (persist / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.failures.json")
    manifest_file = manifest_path or (persist / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.manifest.json")

    resolved_client = client or chromadb.PersistentClient(
        path=str(persist),
        settings=Settings(anonymized_telemetry=False),
    )
    progress = load_progress(progress_file) if resume else _empty_progress()
    completed = set(progress["completed"])

    collection_exists = True
    try:
        resolved_client.get_collection(CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME)
    except Exception:
        collection_exists = False

    should_delete = delete_existing and not (resume and collection_exists and completed)
    if resume and not collection_exists:
        log.warning("resume requested but collection missing; starting a fresh areas build")
        should_delete = True
        progress = _empty_progress()
        completed = set()

    collection = ensure_areas_collection(
        resolved_client,
        delete_existing=should_delete,
        embedding_function=embedding_function,
    )
    if should_delete:
        progress = _empty_progress()
        completed = set()
        save_progress(progress_file, progress)

    jobs: deque[AreaJob] = deque(
        iter_default_area_jobs(
            year_start=year_start,
            year_end=year_end,
            dataset=dataset,
            state_partition_file=state_partition_file,
        )
    )
    queued_keys = {job.key for job in jobs}
    total_planned = len(jobs)
    log.info(
        "areas matrix jobs=%s years=%s-%s include_tracts=%s include_block_groups=%s resume=%s",
        total_planned,
        year_start,
        year_end,
        include_tracts,
        include_block_groups,
        resume,
    )

    processed = 0
    while jobs:
        job = jobs.popleft()
        if job.key in completed:
            continue
        processed += 1
        log.info(
            "AREA_JOB_START key=%s remaining=%s",
            job.key,
            len(jobs),
        )
        try:
            rows = fetch_area_rows(
                job.dataset,
                job.year,
                job.census_token,
                job.partition,
                http_client=http_client,
            )
            upsert_area_rows(
                resolved_client,
                rows,
                batch_size=batch_size,
                collection=collection,
                embedding_function=embedding_function,
            )
        except Exception as exc:
            failure = {"key": job.key, "error": str(exc)}
            progress["failures"].append(failure)
            try:
                save_progress(progress_file, progress)
                write_failures_file(failures_file, progress["failures"])
            except Exception as persist_exc:
                log.error("AREA_JOB_FAILURE_PERSIST key=%s error=%s", job.key, persist_exc)
            log.error("AREA_JOB_FAILURE key=%s error=%s", job.key, exc)
            continue

        completed.add(job.key)
        progress["completed"] = sorted(completed)
        if job.dataset not in progress["datasets"]:
            progress["datasets"].append(job.dataset)
        if job.year not in progress["years"]:
            progress["years"].append(job.year)
        if job.partition.label not in progress["partitions"]:
            progress["partitions"].append(job.partition.label)
        if job.source_url not in progress["source_urls"]:
            progress["source_urls"].append(job.source_url)
        try:
            save_progress(progress_file, progress)
            write_cumulative_area_manifest(
                manifest_file,
                document_count=collection.count(),
                datasets=progress["datasets"],
                years=progress["years"],
                partitions=progress["partitions"],
                source_urls=progress["source_urls"],
            )
        except Exception as persist_exc:
            log.error("AREA_JOB_PERSIST_FAILURE key=%s error=%s", job.key, persist_exc)
        log.info("AREA_JOB_SUCCESS key=%s rows=%s", job.key, len(rows))
        if job.census_token == "county" and (include_tracts or include_block_groups):
            for child in county_child_jobs(
                rows,
                include_tracts=include_tracts,
                include_block_groups=include_block_groups,
            ):
                if child.key not in completed and child.key not in queued_keys:
                    jobs.append(child)
                    queued_keys.add(child.key)

    write_failures_file(failures_file, progress["failures"])
    count = collection.count()
    write_cumulative_area_manifest(
        manifest_file,
        document_count=count,
        datasets=progress["datasets"],
        years=progress["years"],
        partitions=progress["partitions"],
        source_urls=progress["source_urls"],
    )
    log.info(
        "areas build complete document_count=%s completed_jobs=%s failures=%s manifest=%s",
        count,
        len(completed),
        len(progress["failures"]),
        manifest_file,
    )
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the official Census geography area index.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--matrix",
        action="store_true",
        help="Build Option 2 coverage matrix for a year window (orchestrator path).",
    )
    parser.add_argument("--dataset", default=DEFAULT_AREA_DATASET)
    parser.add_argument("--year", type=int, help="Single-year mode (required without --matrix)")
    parser.add_argument("--level", help="Exact Census geography token (single-year mode)")
    parser.add_argument(
        "--partition",
        action="append",
        default=[],
        help="Comma-separated parent clauses, e.g. 'state:06,county:001'",
    )
    parser.add_argument("--partition-file", type=Path)
    parser.add_argument("--year-start", type=int, default=CATALOG_YEAR_START)
    parser.add_argument("--year-end", type=int, default=LATEST_AVAILABLE_YEAR)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--persist-dir", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--include-tracts", action="store_true")
    parser.add_argument("--include-block-groups", action="store_true")
    parser.add_argument(
        "--delete-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    manifest = args.manifest or (args.persist_dir / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.manifest.json")

    if args.matrix:
        build_areas_index(
            args.persist_dir,
            year_start=args.year_start,
            year_end=args.year_end,
            delete_existing=args.delete_existing,
            resume=args.resume,
            include_tracts=args.include_tracts,
            include_block_groups=args.include_block_groups,
            batch_size=args.batch_size,
            dataset=args.dataset,
            state_partition_file=args.partition_file,
            manifest_path=manifest,
        )
        return

    if args.year is None or not args.level:
        raise SystemExit("single-year mode requires --year and --level (or pass --matrix)")

    partitions = load_partitions(args.partition, args.partition_file)
    rows: list[AreaRow] = []
    source_url = f"{BASE_URL}/{args.year}/{args.dataset}"
    for partition in partitions:
        LOGGER.info("enumerating level=%s partition=%s", args.level, partition.label)
        rows.extend(fetch_area_rows(args.dataset, args.year, args.level, partition))

    client = chromadb.PersistentClient(
        path=str(args.persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    upsert_area_rows(client, rows, batch_size=args.batch_size)
    write_area_manifest(manifest, rows=rows, source_urls=[source_url])
    LOGGER.info("indexed %s areas; manifest=%s", len(rows), manifest)


if __name__ == "__main__":
    main()
