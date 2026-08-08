"""One-command rebuild of the active Census Chroma catalog collections."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings
from chromadb.types import Where

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CATALOG_YEAR_START,
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
    LATEST_AVAILABLE_YEAR,
)
from index.build_geography_areas_index import build_areas_index
from index.build_geography_index import build_dataset_geographies_index
from index.build_index_table import CensusTableIndexBuilder
from index.check_geography_index import ACTIVE_CATALOG_COLLECTIONS, check_index_health
from index.promote_chroma import _release_chroma_file_handles, promote_swap
from src.domain.geography_catalog import ProvenanceKind

LOGGER = logging.getLogger("rebuild_catalog")

COMPONENT_TABLES = "tables"
COMPONENT_GEOGRAPHIES = "geographies"
COMPONENT_AREAS = "areas"
COMPONENT_ALL = "all"
SUPPORTED_COMPONENTS = (COMPONENT_TABLES, COMPONENT_GEOGRAPHIES, COMPONENT_AREAS, COMPONENT_ALL)
COMPONENT_TO_COLLECTION = {
    COMPONENT_TABLES: CHROMA_TABLE_COLLECTION_NAME,
    COMPONENT_GEOGRAPHIES: CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    COMPONENT_AREAS: CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
}
_PROVENANCE_KINDS = frozenset({"census_geography", "census_examples", "census_api", "census_groups"})


def _meta_str(metadata: Mapping[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str | int | float | bool):
        raise ValueError(f"metadata {key!r} must be a scalar, got {type(value).__name__}")
    return str(value)


def _meta_int(metadata: Mapping[str, Any], key: str) -> int:
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, int | str | float):
        raise ValueError(f"metadata {key!r} must be int-convertible, got {type(value).__name__}")
    return int(value)


def _meta_provenance(metadata: Mapping[str, Any], key: str = "provenance") -> ProvenanceKind:
    value = _meta_str(metadata, key)
    if value not in _PROVENANCE_KINDS:
        raise ValueError(f"metadata {key!r} must be a ProvenanceKind, got {value!r}")
    return cast(ProvenanceKind, value)


def _resolve_components(raw: list[str]) -> list[str]:
    if COMPONENT_ALL in raw or not raw:
        return [COMPONENT_TABLES, COMPONENT_GEOGRAPHIES, COMPONENT_AREAS]
    ordered: list[str] = []
    for name in (COMPONENT_TABLES, COMPONENT_GEOGRAPHIES, COMPONENT_AREAS):
        if name in raw and name not in ordered:
            ordered.append(name)
    return ordered


def _client(path: Path):
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def copy_collections_from_serving(
    serving: Path,
    staging: Path,
    *,
    collection_names: list[str],
) -> None:
    """Copy selected active collections + manifests from serving into staging for swap completeness."""
    if not collection_names:
        return
    serving_client = _client(serving)
    staging.mkdir(parents=True, exist_ok=True)
    staging_client = _client(staging)

    for name in collection_names:
        try:
            source = serving_client.get_collection(name)
        except Exception as exc:
            raise SystemExit(f"serving is missing {name!r}; cannot copy for promote: {exc}") from exc

        try:
            staging_client.delete_collection(name)
        except Exception:
            pass

        metadata = dict(source.metadata or {})
        destination = staging_client.create_collection(name=name, metadata=metadata or None)
        offset = 0
        batch_size = 500
        while True:
            chunk = source.get(limit=batch_size, offset=offset, include=["documents", "metadatas"])
            ids = chunk["ids"]
            if not ids:
                break
            destination.upsert(ids=ids, documents=chunk["documents"], metadatas=chunk["metadatas"])
            offset += len(ids)
            LOGGER.info("copied %s: %s records", name, offset)

        manifest_src = serving / f"{name}.manifest.json"
        manifest_dst = staging / f"{name}.manifest.json"
        if not manifest_src.exists():
            raise SystemExit(f"serving is missing manifest {manifest_src}")
        shutil.copy2(manifest_src, manifest_dst)
        LOGGER.info("copied manifest %s -> %s", manifest_src, manifest_dst)

    del serving_client
    del staging_client
    _release_chroma_file_handles()


def collections_built_by_components(components: list[str]) -> set[str]:
    return {COMPONENT_TO_COLLECTION[name] for name in components if name in COMPONENT_TO_COLLECTION}


def missing_active_collections(built: set[str]) -> list[str]:
    return [name for name in ACTIVE_CATALOG_COLLECTIONS if name not in built]


def copy_geography_from_serving(serving: Path, staging: Path) -> None:
    """Backward-compatible helper: copy both geography collections from serving."""
    copy_collections_from_serving(
        serving,
        staging,
        collection_names=[
            CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
            CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
        ],
    )


def verify_table_smoke(persist_dir: Path, *, query_text: str = "total population") -> dict[str, object]:
    """Fail closed if table docs are grounded and semantic query returns usable hits."""
    from src.domain.geography_catalog import TableCandidate

    client = _client(persist_dir)
    collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
    sample = collection.get(include=["metadatas"])
    ids = sample["ids"]
    metadatas = sample["metadatas"] or []
    if not ids:
        raise SystemExit("table smoke failed: collection is empty")

    legacy = [candidate_id for candidate_id in ids if not str(candidate_id).startswith("table:")]
    if legacy:
        raise SystemExit(f"table smoke found legacy ids (showing up to 5): {legacy[:5]}")

    for candidate_id, metadata in zip(ids, metadatas, strict=True):
        meta: dict[str, Any] = dict(metadata or {})
        if meta.get("candidate_id") != candidate_id:
            raise SystemExit(f"candidate_id mismatch for {candidate_id}: {meta.get('candidate_id')}")
        years_raw = _meta_str(meta, "years_available") if meta.get("years_available") not in (None, "") else ""
        years = [int(part) for part in years_raw.split(",") if part.strip()]
        display = meta.get("display_name") or meta.get("table_name") or ""
        try:
            TableCandidate(
                candidate_id=_meta_str(meta, "candidate_id"),
                dataset=_meta_str(meta, "dataset"),
                year=_meta_int(meta, "year"),
                display_name=str(display) if isinstance(display, str | int | float | bool) else "",
                provenance=_meta_provenance(meta),
                schema_version=_meta_str(meta, "schema_version"),
                table_code=_meta_str(meta, "table_code"),
                table_name=_meta_str(meta, "table_name"),
                category=_meta_str(meta, "category"),
                years_available=years,
            )
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"table smoke failed for {candidate_id}: {exc}") from exc

    raw = collection.query(query_texts=[query_text], n_results=5, include=["metadatas", "distances"])
    hit_ids = [str(item) for item in (raw.get("ids") or [[]])[0]]
    if not hit_ids:
        raise SystemExit(f"table smoke failed: empty query results for {query_text!r}")
    if any(not item.startswith("table:") for item in hit_ids):
        raise SystemExit(f"table smoke query returned legacy ids: {hit_ids}")

    payload = {
        "status": "hit",
        "query_text": query_text,
        "document_count": len(ids),
        "candidate_ids": hit_ids,
        "schema_version": (collection.metadata or {}).get("schema_version"),
        "index_version": (collection.metadata or {}).get("index_version"),
    }
    return payload


def verify_catalog_health(persist_dir: Path, collections: list[str]) -> list[dict[str, object]]:
    client = _client(persist_dir)
    results = [check_index_health(client, name, persist_dir / f"{name}.manifest.json") for name in collections]
    payload = [asdict(result) for result in results]
    if not all(result.healthy for result in results):
        raise SystemExit(f"catalog health failed: {json.dumps(payload, indent=2)}")
    return payload


def build_tables(staging: Path, *, year_start: int, year_end: int) -> int:
    builder = CensusTableIndexBuilder(persist_dir=staging)
    return builder.build_index(
        year_start=year_start,
        year_end=year_end,
        delete_existing=True,
        manifest_path=staging / f"{CHROMA_TABLE_COLLECTION_NAME}.manifest.json",
    )


def build_geographies(staging: Path, *, year_start: int, year_end: int) -> int:
    return build_dataset_geographies_index(
        staging,
        year_start=year_start,
        year_end=year_end,
        delete_existing=True,
        manifest_path=staging / f"{CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME}.manifest.json",
        logger=LOGGER,
    )


def build_areas(
    staging: Path,
    *,
    year_start: int,
    year_end: int,
    resume: bool = False,
    include_tracts: bool = False,
    include_block_groups: bool = False,
) -> int:
    return build_areas_index(
        staging,
        year_start=year_start,
        year_end=year_end,
        delete_existing=not resume,
        resume=resume,
        include_tracts=include_tracts,
        include_block_groups=include_block_groups,
        manifest_path=staging / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.manifest.json",
        progress_path=staging / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.progress.json",
        failures_path=staging / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.failures.json",
        logger=LOGGER,
    )


def verify_area_smoke(
    persist_dir: Path,
    *,
    query_text: str = "California",
    dataset: str = "acs/acs5",
    year: int | None = None,
) -> dict[str, object]:
    """Fail closed if area docs are grounded and a place/state query hits."""
    from src.domain.geography_catalog import AreaCandidate

    client = _client(persist_dir)
    collection = client.get_collection(CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME)
    sample = collection.get(include=["metadatas"], limit=50)
    ids = sample["ids"]
    metadatas = sample["metadatas"] or []
    if not ids:
        raise SystemExit("area smoke failed: collection is empty")

    legacy = [candidate_id for candidate_id in ids if not str(candidate_id).startswith("geo-area:")]
    if legacy:
        raise SystemExit(f"area smoke found legacy ids (showing up to 5): {legacy[:5]}")

    sample_year = year
    for candidate_id, metadata in zip(ids, metadatas, strict=True):
        meta: dict[str, Any] = dict(metadata or {})
        if meta.get("candidate_id") != candidate_id:
            raise SystemExit(f"candidate_id mismatch for {candidate_id}: {meta.get('candidate_id')}")
        try:
            AreaCandidate(
                candidate_id=_meta_str(meta, "candidate_id"),
                dataset=_meta_str(meta, "dataset"),
                year=_meta_int(meta, "year"),
                display_name=_meta_str(meta, "display_name"),
                provenance=_meta_provenance(meta),
                schema_version=_meta_str(meta, "schema_version"),
                friendly_level=_meta_str(meta, "friendly_level"),
                census_token=_meta_str(meta, "census_token"),
                geo_id=_meta_str(meta, "geo_id"),
                geography_code=_meta_str(meta, "geography_code"),
            )
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"area smoke failed for {candidate_id}: {exc}") from exc
        if sample_year is None and meta.get("dataset") == dataset:
            sample_year = _meta_int(meta, "year")

    if sample_year is None:
        raise SystemExit(f"area smoke failed: no documents for dataset {dataset!r}")

    where = cast(
        Where,
        {"$and": [{"dataset": {"$eq": dataset}}, {"year": {"$eq": sample_year}}]},
    )
    raw = collection.query(
        query_texts=[query_text],
        n_results=5,
        where=where,
        include=["metadatas", "distances"],
    )
    hit_ids = [str(item) for item in (raw.get("ids") or [[]])[0]]
    if not hit_ids:
        raise SystemExit(f"area smoke failed: empty query results for {query_text!r} dataset={dataset} year={sample_year}")
    if any(not item.startswith("geo-area:") for item in hit_ids):
        raise SystemExit(f"area smoke query returned legacy ids: {hit_ids}")

    return {
        "status": "hit",
        "query_text": query_text,
        "dataset": dataset,
        "year": sample_year,
        "document_count": collection.count(),
        "candidate_ids": hit_ids,
        "schema_version": (collection.metadata or {}).get("schema_version"),
        "index_version": (collection.metadata or {}).get("index_version"),
    }


def verify_geography_smoke(
    persist_dir: Path,
    *,
    query_text: str = "county",
    dataset: str = "acs/acs5",
    year: int | None = None,
) -> dict[str, object]:
    """Fail closed if dataset geography docs are grounded and a level query hits."""
    from src.domain.geography_catalog import HierarchyCandidate

    client = _client(persist_dir)
    collection = client.get_collection(CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME)
    sample = collection.get(include=["metadatas"])
    ids = sample["ids"]
    metadatas = sample["metadatas"] or []
    if not ids:
        raise SystemExit("geography smoke failed: collection is empty")

    legacy = [candidate_id for candidate_id in ids if not str(candidate_id).startswith("geo-level:")]
    if legacy:
        raise SystemExit(f"geography smoke found legacy ids (showing up to 5): {legacy[:5]}")

    sample_year = year
    for candidate_id, metadata in zip(ids, metadatas, strict=True):
        meta: dict[str, Any] = dict(metadata or {})
        if meta.get("candidate_id") != candidate_id:
            raise SystemExit(f"candidate_id mismatch for {candidate_id}: {meta.get('candidate_id')}")
        hierarchy = meta.get("geography_hierarchy") or meta.get("display_name") or ""
        try:
            HierarchyCandidate(
                candidate_id=_meta_str(meta, "candidate_id"),
                dataset=_meta_str(meta, "dataset"),
                year=_meta_int(meta, "year"),
                display_name=str(hierarchy) if isinstance(hierarchy, str | int | float | bool) else "",
                provenance=_meta_provenance(meta),
                schema_version=_meta_str(meta, "schema_version"),
                friendly_level=_meta_str(meta, "friendly_level"),
                census_token=_meta_str(meta, "census_token"),
                hierarchy=_meta_str(meta, "geography_hierarchy"),
            )
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"geography smoke failed for {candidate_id}: {exc}") from exc
        if sample_year is None and meta.get("dataset") == dataset:
            sample_year = _meta_int(meta, "year")

    if sample_year is None:
        raise SystemExit(f"geography smoke failed: no documents for dataset {dataset!r}")

    where = cast(
        Where,
        {"$and": [{"dataset": {"$eq": dataset}}, {"year": {"$eq": sample_year}}]},
    )
    raw = collection.query(
        query_texts=[query_text],
        n_results=5,
        where=where,
        include=["metadatas", "distances"],
    )
    hit_ids = [str(item) for item in (raw.get("ids") or [[]])[0]]
    if not hit_ids:
        raise SystemExit(
            f"geography smoke failed: empty query results for {query_text!r} dataset={dataset} year={sample_year}"
        )
    if any(not item.startswith("geo-level:") for item in hit_ids):
        raise SystemExit(f"geography smoke query returned legacy ids: {hit_ids}")

    return {
        "status": "hit",
        "query_text": query_text,
        "dataset": dataset,
        "year": sample_year,
        "document_count": len(ids),
        "candidate_ids": hit_ids,
        "schema_version": (collection.metadata or {}).get("schema_version"),
        "index_version": (collection.metadata or {}).get("index_version"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--serving", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument("--year-start", type=int, default=CATALOG_YEAR_START)
    parser.add_argument("--year-end", type=int, default=LATEST_AVAILABLE_YEAR)
    parser.add_argument(
        "--components",
        action="append",
        choices=SUPPORTED_COMPONENTS,
        help="Repeatable. Default without flag: tables. Supported: tables, geographies, areas, all.",
    )
    parser.add_argument("--promote", action="store_true", help="Swap staging into serving after verify.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted areas matrix build.")
    parser.add_argument(
        "--include-tracts",
        action="store_true",
        help="Opt-in: after county jobs, enumerate tracts under each county (long).",
    )
    parser.add_argument(
        "--include-block-groups",
        action="store_true",
        help="Opt-in: after county jobs, enumerate block groups under each county (very long).",
    )
    parser.add_argument(
        "--stamp",
        default=None,
        help="Backup stamp for promote (default: promote_chroma timestamp).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.year_end < args.year_start:
        raise SystemExit("--year-end must be >= --year-start")

    components = _resolve_components(args.components or [COMPONENT_TABLES])

    LOGGER.info(
        "rebuild_catalog staging=%s serving=%s years=%s-%s components=%s resume=%s",
        args.staging,
        args.serving,
        args.year_start,
        args.year_end,
        components,
        args.resume,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "staging": str(args.staging),
                    "serving": str(args.serving),
                    "year_start": args.year_start,
                    "year_end": args.year_end,
                    "components": components,
                    "promote": args.promote,
                    "resume": args.resume,
                    "include_tracts": args.include_tracts,
                    "include_block_groups": args.include_block_groups,
                },
                indent=2,
            )
        )
        return

    args.staging.mkdir(parents=True, exist_ok=True)

    if COMPONENT_TABLES in components:
        count = build_tables(args.staging, year_start=args.year_start, year_end=args.year_end)
        LOGGER.info("built census_tables document_count=%s", count)

    if COMPONENT_GEOGRAPHIES in components:
        count = build_geographies(args.staging, year_start=args.year_start, year_end=args.year_end)
        LOGGER.info("built census_dataset_geographies document_count=%s", count)

    if COMPONENT_AREAS in components:
        count = build_areas(
            args.staging,
            year_start=args.year_start,
            year_end=args.year_end,
            resume=args.resume,
            include_tracts=args.include_tracts,
            include_block_groups=args.include_block_groups,
        )
        LOGGER.info("built census_geography_areas document_count=%s", count)

    health_collections = [COMPONENT_TO_COLLECTION[name] for name in components if name in COMPONENT_TO_COLLECTION]
    if not args.skip_verify:
        if health_collections:
            health = verify_catalog_health(args.staging, health_collections)
            LOGGER.info("health ok: %s", health)
        if COMPONENT_TABLES in components:
            smoke = verify_table_smoke(args.staging)
            LOGGER.info("table smoke ok: %s", smoke)
        if COMPONENT_GEOGRAPHIES in components:
            smoke = verify_geography_smoke(args.staging)
            LOGGER.info("geography smoke ok: %s", smoke)
        if COMPONENT_AREAS in components:
            smoke = verify_area_smoke(args.staging)
            LOGGER.info("area smoke ok: %s", smoke)

    if not args.promote:
        LOGGER.info("build complete; pass --promote to swap into serving")
        return

    # Swap requires all three active collections in staging; copy anything not rebuilt.
    to_copy = missing_active_collections(collections_built_by_components(components))
    copy_collections_from_serving(args.serving, args.staging, collection_names=to_copy)
    if not args.skip_verify:
        verify_catalog_health(args.staging, list(ACTIVE_CATALOG_COLLECTIONS))
    _release_chroma_file_handles()

    from datetime import datetime

    stamp = args.stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    promote_swap(
        staging=args.staging,
        serving=args.serving,
        stamp=stamp,
        skip_backup=False,
        dry_run=False,
    )
    LOGGER.info("promoted staging -> %s", args.serving)


if __name__ == "__main__":
    main()
