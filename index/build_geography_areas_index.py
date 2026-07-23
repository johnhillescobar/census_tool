"""Build-time Census area enumeration for the geography areas Chroma index."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chromadb
import requests
from chromadb.api import ClientAPI
from chromadb.config import Settings

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CENSUS_API_TIMEOUT,
    CENSUS_CATALOG_INDEX_VERSION,
    CENSUS_CATALOG_SCHEMA_VERSION,
    CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
)
from index.build_geography_index import _create_embedding_function
from src.domain.geography_catalog import IndexManifest

LOGGER = logging.getLogger("geography_areas_index")
BASE_URL = "https://api.census.gov/data"


class HttpClient(Protocol):
    def get(self, url: str, *, params: dict[str, str], timeout: int): ...


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
    return params


def fetch_area_rows(
    dataset: str,
    year: int,
    census_token: str,
    partition: AreaPartition,
    *,
    http_client: HttpClient = requests,
) -> list[AreaRow]:
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


def upsert_area_rows(
    client: ClientAPI,
    rows: Sequence[AreaRow],
    *,
    batch_size: int = 500,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    collection = client.get_or_create_collection(
        CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
        metadata={
            "description": "Official Census NAME,GEO_ID geography enumeration",
            "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
            "index_version": CENSUS_CATALOG_INDEX_VERSION,
        },
        embedding_function=_create_embedding_function(),
    )
    unique_rows = {stable_area_id(row): row for row in rows}
    ordered = [unique_rows[candidate_id] for candidate_id in sorted(unique_rows)]
    for start in range(0, len(ordered), batch_size):
        batch = ordered[start : start + batch_size]
        collection.upsert(
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
    manifest = IndexManifest(
        collection_name=CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME,
        schema_version=CENSUS_CATALOG_SCHEMA_VERSION,
        index_version=CENSUS_CATALOG_INDEX_VERSION,
        document_count=len(unique_rows),
        datasets=sorted({row.dataset for row in unique_rows.values()}),
        years=sorted({row.year for row in unique_rows.values()}),
        source_urls=sorted(set(source_urls)),
        partitions=sorted({row.partition.label for row in unique_rows.values()}),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def load_partitions(values: Sequence[str], partition_file: Path | None) -> list[AreaPartition]:
    raw_values = list(values)
    if partition_file:
        payload = json.loads(partition_file.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise ValueError("partition file must contain a JSON list of LEVEL:VALUE strings")
        raw_values.extend(payload)
    return [parse_partition(value) for value in raw_values] or [AreaPartition()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the official Census geography area index.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--level", required=True, help="Exact Census geography token")
    parser.add_argument(
        "--partition",
        action="append",
        default=[],
        help="Comma-separated parent clauses, e.g. 'state:06,county:001'",
    )
    parser.add_argument("--partition-file", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--persist-dir", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(CHROMA_PERSIST_DIRECTORY) / f"{CHROMA_GEOGRAPHY_AREAS_COLLECTION_NAME}.manifest.json",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
    write_area_manifest(args.manifest, rows=rows, source_urls=[source_url])
    LOGGER.info("indexed %s areas; manifest=%s", len(rows), args.manifest)


if __name__ == "__main__":
    main()
