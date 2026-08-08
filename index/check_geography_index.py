"""Offline health checks for the active Census Chroma catalog collections."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CENSUS_CATALOG_INDEX_VERSION,
    CENSUS_CATALOG_SCHEMA_VERSION,
    CENSUS_GEOGRAPHY_INDEX_MAX_AGE_SECONDS,
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
)
from src.domain.geography_catalog import IndexManifest

# Geography-only default kept for backward-compatible CLI/tests.
DEFAULT_COLLECTIONS = (
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
)

ACTIVE_CATALOG_COLLECTIONS = (
    CHROMA_TABLE_COLLECTION_NAME,
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
)


@dataclass(frozen=True)
class IndexHealth:
    collection_name: str
    healthy: bool
    document_count: int = 0
    reason: str | None = None
    manifest_age_seconds: float | None = None


def check_index_health(
    client: ClientAPI,
    collection_name: str,
    manifest_path: Path,
    *,
    max_age_seconds: int = CENSUS_GEOGRAPHY_INDEX_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> IndexHealth:
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        return IndexHealth(collection_name, False, reason=f"collection_unavailable: {exc}")

    count = collection.count()
    metadata = collection.metadata or {}
    if metadata.get("schema_version") != CENSUS_CATALOG_SCHEMA_VERSION:
        return IndexHealth(collection_name, False, count, "schema_mismatch")
    if metadata.get("index_version") != CENSUS_CATALOG_INDEX_VERSION:
        return IndexHealth(collection_name, False, count, "index_version_mismatch")
    if count <= 0:
        return IndexHealth(collection_name, False, count, "empty")
    if not manifest_path.exists():
        return IndexHealth(collection_name, False, count, "manifest_missing")

    try:
        manifest = IndexManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        return IndexHealth(collection_name, False, count, f"manifest_invalid: {exc}")
    if manifest.collection_name != collection_name:
        return IndexHealth(collection_name, False, count, "manifest_collection_mismatch")
    if manifest.schema_version != CENSUS_CATALOG_SCHEMA_VERSION:
        return IndexHealth(collection_name, False, count, "manifest_schema_mismatch")
    if manifest.index_version != CENSUS_CATALOG_INDEX_VERSION:
        return IndexHealth(collection_name, False, count, "manifest_index_version_mismatch")
    if manifest.document_count != count:
        return IndexHealth(collection_name, False, count, "manifest_count_mismatch")

    checked_at = now or datetime.now(UTC)
    built_at = manifest.built_at
    if built_at.tzinfo is None:
        built_at = built_at.replace(tzinfo=UTC)
    age = max(0.0, (checked_at - built_at).total_seconds())
    if age > max_age_seconds:
        return IndexHealth(collection_name, False, count, "stale", age)
    return IndexHealth(collection_name, True, count, manifest_age_seconds=age)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local Census Chroma catalog indexes.")
    parser.add_argument("--persist-dir", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument(
        "--collection",
        action="append",
        choices=ACTIVE_CATALOG_COLLECTIONS,
        help="Repeatable. Default without --all: geography collections only.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all active catalog collections (tables + geography).",
    )
    parser.add_argument("--max-age-seconds", type=int, default=CENSUS_GEOGRAPHY_INDEX_MAX_AGE_SECONDS)
    args = parser.parse_args()

    client = chromadb.PersistentClient(
        path=str(args.persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    if args.collection:
        collections = args.collection
    elif args.all:
        collections = list(ACTIVE_CATALOG_COLLECTIONS)
    else:
        collections = list(DEFAULT_COLLECTIONS)
    results = [
        check_index_health(
            client,
            name,
            args.persist_dir / f"{name}.manifest.json",
            max_age_seconds=args.max_age_seconds,
        )
        for name in collections
    ]
    print(json.dumps([asdict(result) for result in results], indent=2))
    if not all(result.healthy for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
