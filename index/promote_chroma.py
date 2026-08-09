"""Promote validated Chroma index builds from staging into the serving directory."""

from __future__ import annotations

import argparse
import gc
import json
import logging
import shutil
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CENSUS_CATALOG_INDEX_VERSION,
    CENSUS_CATALOG_SCHEMA_VERSION,
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
)
from index.check_geography_index import DEFAULT_COLLECTIONS, check_index_health
from src.domain.geography_catalog import IndexManifest

LOGGER = logging.getLogger("promote_chroma")
GEOGRAPHY_COLLECTIONS = DEFAULT_COLLECTIONS
REQUIRED_SERVING_COLLECTIONS = (CHROMA_TABLE_COLLECTION_NAME, *GEOGRAPHY_COLLECTIONS)
UPSERT_BATCH_SIZE = 500


def _metadata_str(metadata: Mapping[str, object], key: str) -> str:
    return str(metadata[key])


def _metadata_int(metadata: Mapping[str, object], key: str) -> int:
    value = metadata[key]
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return int(str(value))


def _client(path: Path) -> ClientAPI:
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def _release_chroma_file_handles() -> None:
    """Drop PersistentClient singletons so Windows can rename/delete Chroma dirs."""
    try:
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:
        LOGGER.debug("chroma system cache clear unavailable", exc_info=True)
    gc.collect()


def _replace_directory(source: Path, destination: Path, *, retries: int = 5) -> None:
    """Move/replace directories with Windows-friendly retries for locked files."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        _release_chroma_file_handles()
        try:
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(source), str(destination))
            return
        except PermissionError as exc:
            last_error = exc
            LOGGER.warning(
                "directory move blocked (attempt %s/%s): %s -> %s (%s)",
                attempt,
                retries,
                source,
                destination,
                exc,
            )
            time.sleep(min(2 * attempt, 8))
    raise SystemExit(f"failed to move {source} -> {destination}: {last_error}")


def _collection_count(client: ClientAPI, name: str) -> int | None:
    try:
        return client.get_collection(name).count()
    except Exception:
        return None


def _require_collection(client: ClientAPI, name: str, *, location: str) -> int:
    count = _collection_count(client, name)
    if count is None:
        raise SystemExit(f"{location} is missing collection {name!r}")
    if count <= 0:
        raise SystemExit(f"{location} collection {name!r} is empty")
    return count


def _backup_serving(serving: Path, stamp: str) -> Path:
    backup = serving.parent / f"{serving.name}-previous-{stamp}"
    if backup.exists():
        raise SystemExit(f"backup path already exists: {backup}")
    LOGGER.info("backing up %s -> %s", serving, backup)
    shutil.copytree(serving, backup)
    return backup


def _merge_collection(
    *,
    source: ClientAPI,
    destination: ClientAPI,
    collection_name: str,
    batch_size: int = UPSERT_BATCH_SIZE,
) -> tuple[int, int]:
    src = source.get_collection(collection_name)
    dst = destination.get_collection(collection_name)
    before = dst.count()
    offset = 0
    copied = 0
    while True:
        chunk = src.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"],
        )
        ids = chunk["ids"]
        if not ids:
            break
        dst.upsert(ids=ids, documents=chunk["documents"], metadatas=chunk["metadatas"])
        copied += len(ids)
        offset += len(ids)
        LOGGER.info("merged %s: %s records", collection_name, copied)
    after = dst.count()
    return before, after


def _write_area_manifest(path: Path, *, count: int, metadatas: Sequence[Mapping[str, object]]) -> None:
    datasets = sorted({_metadata_str(item, "dataset") for item in metadatas})
    years = sorted({_metadata_int(item, "year") for item in metadatas})
    partitions = sorted({_metadata_str(item, "partition") for item in metadatas if item.get("partition")})
    source_urls = sorted(
        {f"https://api.census.gov/data/{_metadata_int(item, 'year')}/{_metadata_str(item, 'dataset')}" for item in metadatas}
    )
    manifest = IndexManifest.model_validate(
        {
            "collection_name": CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
            "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
            "index_version": CENSUS_CATALOG_INDEX_VERSION,
            "document_count": count,
            "datasets": datasets,
            "years": years,
            "source_urls": source_urls,
            "partitions": partitions,
        }
    )
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def _write_hierarchy_manifest(path: Path, *, count: int, metadatas: Sequence[Mapping[str, object]]) -> None:
    datasets = sorted({_metadata_str(item, "dataset") for item in metadatas})
    years = sorted({_metadata_int(item, "year") for item in metadatas})
    source_urls = sorted({_metadata_str(item, "source_url") for item in metadatas if item.get("source_url")})
    manifest = IndexManifest.model_validate(
        {
            "collection_name": CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
            "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
            "index_version": CENSUS_CATALOG_INDEX_VERSION,
            "document_count": count,
            "datasets": datasets,
            "years": years,
            "source_urls": source_urls,
        }
    )
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def _refresh_manifests(serving: Path, collections: Iterable[str]) -> None:
    client = _client(serving)
    for collection_name in collections:
        collection = client.get_collection(collection_name)
        count = collection.count()
        raw_metadatas = collection.get(include=["metadatas"])["metadatas"] or []
        metadatas = cast(Sequence[Mapping[str, object]], raw_metadatas)
        manifest_path = serving / f"{collection_name}.manifest.json"
        if collection_name == CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME:
            _write_area_manifest(manifest_path, count=count, metadatas=metadatas)
        elif collection_name == CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME:
            _write_hierarchy_manifest(manifest_path, count=count, metadatas=metadatas)
        else:
            raise ValueError(f"unsupported manifest refresh for {collection_name!r}")
        LOGGER.info("wrote manifest %s (document_count=%s)", manifest_path, count)


def _print_health(serving: Path) -> None:
    client = _client(serving)
    results = [check_index_health(client, name, serving / f"{name}.manifest.json") for name in GEOGRAPHY_COLLECTIONS]
    print(json.dumps([result.__dict__ for result in results], indent=2))
    if not all(result.healthy for result in results):
        raise SystemExit("post-promotion geography health check failed")


def promote_merge_geography(
    *,
    staging: Path,
    serving: Path,
    collections: Sequence[str],
    stamp: str,
    skip_backup: bool,
    dry_run: bool,
) -> None:
    if not staging.is_dir():
        raise SystemExit(f"staging directory not found: {staging}")
    if not serving.is_dir():
        raise SystemExit(f"serving directory not found: {serving}")

    staging_client = _client(staging)
    serving_client = _client(serving)

    _require_collection(serving_client, CHROMA_TABLE_COLLECTION_NAME, location=str(serving))
    for name in collections:
        _require_collection(staging_client, name, location=str(staging))

    if dry_run:
        print("dry run: would merge geography collections from staging into serving")
        for name in collections:
            print(
                f"  {name}: staging={_collection_count(staging_client, name)} "
                f"serving={_collection_count(serving_client, name)}"
            )
        return

    if not skip_backup:
        _backup_serving(serving, stamp)

    for name in collections:
        before, after = _merge_collection(source=staging_client, destination=serving_client, collection_name=name)
        LOGGER.info("%s serving count %s -> %s", name, before, after)

    _refresh_manifests(serving, collections)


def promote_swap(
    *,
    staging: Path,
    serving: Path,
    stamp: str,
    skip_backup: bool,
    dry_run: bool,
) -> None:
    if not staging.is_dir():
        raise SystemExit(f"staging directory not found: {staging}")
    if not serving.is_dir():
        raise SystemExit(f"serving directory not found: {serving}")

    staging_client = _client(staging)
    for name in REQUIRED_SERVING_COLLECTIONS:
        _require_collection(staging_client, name, location=str(staging))
    counts = {name: _collection_count(staging_client, name) for name in REQUIRED_SERVING_COLLECTIONS}
    del staging_client
    _release_chroma_file_handles()

    if dry_run:
        print("dry run: would swap staging directory into serving")
        for name, count in counts.items():
            print(f"  {name}: staging={count}")
        return

    backup = serving.parent / f"{serving.name}-previous-{stamp}"
    promoted = serving.parent / f"{serving.name}-promoted-{stamp}"
    if backup.exists() or promoted.exists():
        raise SystemExit("backup or promoted path already exists; choose a new stamp")

    if not skip_backup:
        LOGGER.info("backing up %s -> %s", serving, backup)
        _replace_directory(serving, backup)
    else:
        LOGGER.info("removing serving directory %s", serving)
        _release_chroma_file_handles()
        shutil.rmtree(serving)

    LOGGER.info("moving staging %s -> %s", staging, serving)
    _replace_directory(staging, serving)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("merge-geography", "swap"),
        default="merge-geography",
        help=(
            "merge-geography upserts geography collections from staging into serving "
            "(keeps census_tables). swap replaces the entire serving directory."
        ),
    )
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--serving", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument(
        "--collection",
        action="append",
        choices=GEOGRAPHY_COLLECTIONS,
        help="Geography collection to merge (default: both hierarchy and areas)",
    )
    parser.add_argument("--stamp", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-health", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.mode == "swap":
        promote_swap(
            staging=args.staging,
            serving=args.serving,
            stamp=args.stamp,
            skip_backup=args.skip_backup,
            dry_run=args.dry_run,
        )
    else:
        collections = args.collection or list(GEOGRAPHY_COLLECTIONS)
        promote_merge_geography(
            staging=args.staging,
            serving=args.serving,
            collections=collections,
            stamp=args.stamp,
            skip_backup=args.skip_backup,
            dry_run=args.dry_run,
        )

    if args.dry_run or args.skip_health:
        return
    _print_health(args.serving)


if __name__ == "__main__":
    main()
