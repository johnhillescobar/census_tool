"""
Build the census_geography_hierarchies Chroma collection from Census example tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import chromadb
import requests
from bs4 import BeautifulSoup, Tag
from chromadb.api import ClientAPI
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CENSUS_CATALOG_INDEX_VERSION,
    CENSUS_CATALOG_SCHEMA_VERSION,
    CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
    CHROMA_EMBEDDING_MODEL,
    CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    DEFAULT_DATASETS,
)
from src.domain.geography_catalog import IndexManifest

LOGGER = logging.getLogger("geography_index")

load_dotenv()


@dataclass(frozen=True)
class ExampleRow:
    category: str
    dataset: str
    year: int
    geography_hierarchy: str
    geography_level: str
    example_url: str
    notes: list[str]


@dataclass(frozen=True)
class GeographyRow:
    category: str
    dataset: str
    year: int
    geography_hierarchy: str
    census_token: str
    summary_level: str
    source_url: str
    aliases: tuple[str, ...] = ()


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def build_logger(log_dir: Path) -> logging.Logger:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    absolute_dir = (WORKSPACE_ROOT / log_dir).resolve()
    absolute_dir.mkdir(parents=True, exist_ok=True)
    log_path = absolute_dir / f"{ts}-hierarchy-index.txt"

    logger = logging.getLogger("geography_index")
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    print(f"[build_geography_index] logging to {log_path}")
    return logger


def iter_source_pages(
    datasets: Iterable[tuple[str, Iterable[int]]],
) -> Iterable[tuple[str, str, int, str]]:
    category_map = {
        "acs/acs5": "detail",
        "acs/acs5/subject": "subject",
        "acs/acs1/profile": "profile",
        "acs/acs5/cprofile": "cprofile",
        "acs/acs1/spp": "spp",
    }
    for dataset, years in datasets:
        category = category_map.get(dataset, dataset)
        for year in years:
            url = f"https://api.census.gov/data/{year}/{dataset}/geography.html"
            yield category, dataset, year, url


def iter_example_pages(
    datasets: Iterable[tuple[str, Iterable[int]]],
) -> Iterable[tuple[str, str, int, str]]:
    for category, dataset, year, _ in iter_source_pages(datasets):
        yield category, dataset, year, f"https://api.census.gov/data/{year}/{dataset}/examples.html"


def extract_cell_text(cell: Tag, base_url: str) -> str:
    link = cell.find("a", href=True)
    if link and link["href"].strip():
        href = link["href"].strip()
        if href.startswith(("http://", "https://")):
            return href
        return f"https://{requests.utils.urlparse(base_url).netloc}{href}"
    code = cell.find("code")
    if code:
        return code.get_text(" ", strip=True)
    return cell.get_text(" ", strip=True)


def parse_table(category: str, dataset: str, year: int, table: Tag, base_url: str) -> list[ExampleRow]:
    rows = table.find_all("tr")
    if not rows:
        return []

    headers = [cell.get_text(" ", strip=True).lower() for cell in rows[0].find_all(["th", "td"])]
    notes: list[str] = []
    parsed_rows: list[ExampleRow] = []

    current_hierarchy = ""
    current_level = ""
    for row in rows[1:]:
        cells = [extract_cell_text(cell, base_url) for cell in row.find_all(["th", "td"]) if cell.get_text(strip=True)]
        if not cells:
            continue
        if len(cells) == 1 and len(headers) > 1:
            notes.append(cells[0])
            continue

        zipped = dict(zip(headers, cells))
        hierarchy = zipped.get("geography hierarchy", current_hierarchy)
        level = zipped.get("geography level", current_level)

        example = zipped.get("example url") or zipped.get("example", "")
        if not example:
            continue

        current_hierarchy = hierarchy
        current_level = level

        parsed_rows.append(
            ExampleRow(
                category=category,
                dataset=dataset,
                year=year,
                geography_hierarchy=hierarchy,
                geography_level=level,
                example_url=example,
                notes=notes[:],
            )
        )
    return parsed_rows


def friendly_level_from_token(census_token: str) -> str:
    """Return a searchable label without changing the authoritative token."""
    friendly = census_token.lower().replace("(or part)", "").strip()
    friendly = " ".join(friendly.split())
    return friendly


def hierarchy_tokens(hierarchy: str) -> list[str]:
    """Split a Census hierarchy while preserving each canonical token."""
    return [part.strip() for part in hierarchy.split("›") if part.strip()]


def parse_geography_table(
    category: str,
    dataset: str,
    year: int,
    table: Tag,
    source_url: str,
) -> list[GeographyRow]:
    rows = table.find_all("tr")
    if not rows:
        return []
    headers = [cell.get_text(" ", strip=True).lower() for cell in rows[0].find_all(["th", "td"])]
    parsed: list[GeographyRow] = []
    for row in rows[1:]:
        values = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if not any(values):
            continue
        record = dict(zip(headers, values))
        hierarchy = record.get("geography hierarchy") or record.get("hierarchy") or ""
        summary_level = (
            record.get("geography level")
            or record.get("summary level")
            or record.get("summary level code")
            or ""
        )
        tokens = hierarchy_tokens(hierarchy)
        census_token = tokens[-1] if tokens else record.get("name", "")
        if not hierarchy or not census_token:
            continue
        aliases = tuple(dict.fromkeys([friendly_level_from_token(census_token), *tokens]))
        parsed.append(
            GeographyRow(
                category=category,
                dataset=dataset,
                year=year,
                geography_hierarchy=hierarchy,
                census_token=census_token,
                summary_level=summary_level,
                source_url=source_url,
                aliases=aliases,
            )
        )
    return parsed


def fetch_examples(category: str, dataset: str, year: int, url: str, logger: logging.Logger) -> list[ExampleRow]:
    start = monotonic()
    logger.info("FETCH_START category=%s year=%s url=%s", category, year, url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("no table elements found")

    rows: list[ExampleRow] = []
    for table in tables:
        rows.extend(parse_table(category, dataset, year, table, url))

    logger.info(
        "FETCH_SUCCESS category=%s year=%s count=%s duration=%.2fs",
        category,
        year,
        len(rows),
        monotonic() - start,
    )
    return rows


def fetch_geographies(
    category: str,
    dataset: str,
    year: int,
    url: str,
    logger: logging.Logger,
) -> list[GeographyRow]:
    start = monotonic()
    logger.info("FETCH_START category=%s year=%s url=%s", category, year, url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows = [
        item
        for table in soup.find_all("table")
        for item in parse_geography_table(category, dataset, year, table, url)
    ]
    if not rows:
        raise RuntimeError("no authoritative geography rows found")
    logger.info(
        "FETCH_SUCCESS category=%s year=%s count=%s duration=%.2fs",
        category,
        year,
        len(rows),
        monotonic() - start,
    )
    return rows


def summarize_by_hierarchy(rows: list[ExampleRow]) -> dict[tuple[str, int, str], dict]:
    grouped: dict[tuple[str, int, str], dict] = defaultdict(lambda: {"examples": [], "levels": set(), "notes": set()})

    for row in rows:
        key = (row.dataset, row.year, row.geography_hierarchy)
        grouped[key]["category"] = row.category
        grouped[key]["dataset"] = row.dataset
        grouped[key]["year"] = row.year
        grouped[key]["hierarchy"] = row.geography_hierarchy
        grouped[key]["level_code"] = row.geography_level
        grouped[key]["examples"].append(row.example_url)
        grouped[key]["notes"].update(row.notes)

    return grouped


def stable_geography_id(dataset: str, year: int, hierarchy: str, census_token: str) -> str:
    canonical = "\x1f".join((dataset, str(year), hierarchy, census_token))
    return f"geo-level:{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"


def summarize_geography_levels(
    geographies: list[GeographyRow],
    examples: list[ExampleRow],
) -> dict[str, dict[str, object]]:
    example_map: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    for row in examples:
        key = (row.dataset, row.year, row.geography_hierarchy)
        if row.example_url not in example_map[key]:
            example_map[key].append(row.example_url)

    documents: dict[str, dict[str, object]] = {}
    for row in geographies:
        candidate_id = stable_geography_id(
            row.dataset,
            row.year,
            row.geography_hierarchy,
            row.census_token,
        )
        documents[candidate_id] = {
            "candidate_id": candidate_id,
            "category": row.category,
            "dataset": row.dataset,
            "year": row.year,
            "hierarchy": row.geography_hierarchy,
            "census_token": row.census_token,
            "friendly_level": friendly_level_from_token(row.census_token),
            "summary_level": row.summary_level,
            "aliases": list(row.aliases),
            "source_url": row.source_url,
            "example_urls": example_map.get(
                (row.dataset, row.year, row.geography_hierarchy),
                [],
            ),
        }
    return documents


def build_document(hierarchy: str, ordering: list[str], level_code: str, example_url: str) -> str:
    ordering_clause = " → ".join(ordering) if ordering else "n/a"
    return (
        f"Geography hierarchy: {hierarchy}. "
        f"Ordering: {ordering_clause}. "
        f"Summary level code: {level_code}. "
        f"Example: {example_url}"
    )


def build_metadata(dataset: str, year: int, hierarchy: str, level_code: str, examples: list[str]) -> dict[str, object]:
    parts = hierarchy_tokens(hierarchy)
    for_level = parts[-1] if parts else ""
    candidate_id = stable_geography_id(dataset, year, hierarchy, for_level)
    ordering_list = json.dumps(parts[:-1])
    return {
        "candidate_id": candidate_id,
        "dataset": dataset,
        "table_category": dataset,
        "year": year,
        "geography_hierarchy": hierarchy,
        "geography_level": level_code,
        "census_token": for_level,
        "friendly_level": friendly_level_from_token(for_level),
        "for_level": for_level,
        "ordering_list": ordering_list,
        "aliases": json.dumps(list(dict.fromkeys(parts))),
        "example_urls": json.dumps(examples),
        "provenance": "census_examples",
        "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
        "index_version": CENSUS_CATALOG_INDEX_VERSION,
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


class _DummyEmbeddingFunction:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def __call__(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return [[0.0] for _ in texts]


def _create_embedding_function():
    api_key = os.getenv("CHROMA_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        LOGGER.warning("CHROMA_OPENAI_API_KEY not set. Using dummy embedding function during offline execution.")
        return _DummyEmbeddingFunction(CHROMA_EMBEDDING_MODEL)
    return OpenAIEmbeddingFunction(model_name=CHROMA_EMBEDDING_MODEL)


def upsert_documents(client: ClientAPI, docs: dict[tuple[str, int, str], dict]) -> None:
    embedding_function = _create_embedding_function()
    collection = client.get_or_create_collection(
        CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
        metadata={"description": "Census geography hierarchy ordering examples"},
        embedding_function=embedding_function,
    )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, object]] = []

    for (dataset, year, hierarchy), payload in docs.items():
        hierarchy_parts = [part.strip() for part in hierarchy.split("›") if part.strip()]
        doc_id = stable_geography_id(dataset, year, hierarchy, hierarchy_parts[-1] if hierarchy_parts else "")
        ids.append(doc_id)

        ordering_parts = hierarchy_parts
        canonical_example = payload["examples"][0] if payload["examples"] else ""

        documents.append(
            build_document(
                hierarchy=payload["hierarchy"],
                ordering=ordering_parts[:-1],
                level_code=payload["level_code"],
                example_url=canonical_example,
            )
        )
        metadatas.append(
            build_metadata(
                dataset=payload["dataset"],
                year=payload["year"],
                hierarchy=payload["hierarchy"],
                level_code=payload["level_code"],
                examples=payload["examples"],
            )
        )

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)


def _geography_level_metadata(payload: dict[str, object]) -> dict[str, object]:
    hierarchy = str(payload["hierarchy"])
    parents = hierarchy_tokens(hierarchy)[:-1]
    return {
        "candidate_id": str(payload["candidate_id"]),
        "dataset": str(payload["dataset"]),
        "table_category": str(payload["category"]),
        "year": int(payload["year"]),
        "geography_hierarchy": hierarchy,
        "summary_level": str(payload["summary_level"]),
        "census_token": str(payload["census_token"]),
        "friendly_level": str(payload["friendly_level"]),
        "parent_census_tokens": json.dumps(parents),
        "aliases": json.dumps(payload["aliases"]),
        "example_urls": json.dumps(payload["example_urls"]),
        "source_url": str(payload["source_url"]),
        "provenance": "census_geography",
        "examples_provenance": "census_examples",
        "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
        "index_version": CENSUS_CATALOG_INDEX_VERSION,
    }


def upsert_geography_levels(
    client: ClientAPI,
    docs: dict[str, dict[str, object]],
    *,
    batch_size: int = 500,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    collection = client.get_or_create_collection(
        CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
        metadata={
            "description": "Authoritative Census dataset geography levels",
            "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
            "index_version": CENSUS_CATALOG_INDEX_VERSION,
        },
        embedding_function=_create_embedding_function(),
    )
    items = sorted(docs.items())
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        collection.upsert(
            ids=[candidate_id for candidate_id, _ in batch],
            documents=[
                build_document(
                    hierarchy=str(payload["hierarchy"]),
                    ordering=hierarchy_tokens(str(payload["hierarchy"]))[:-1],
                    level_code=str(payload["summary_level"]),
                    example_url=next(iter(payload["example_urls"]), ""),
                )
                for _, payload in batch
            ],
            metadatas=[_geography_level_metadata(payload) for _, payload in batch],
        )
    return len(items)


def write_manifest(
    path: Path,
    *,
    document_count: int,
    docs: dict[str, dict[str, object]],
) -> IndexManifest:
    manifest = IndexManifest(
        collection_name=CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME,
        schema_version=CENSUS_CATALOG_SCHEMA_VERSION,
        index_version=CENSUS_CATALOG_INDEX_VERSION,
        document_count=document_count,
        datasets=sorted({str(payload["dataset"]) for payload in docs.values()}),
        years=sorted({int(payload["year"]) for payload in docs.values()}),
        source_urls=sorted({str(payload["source_url"]) for payload in docs.values()}),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build authoritative Census dataset geography index.")
    parser.add_argument("--log-dir", type=Path, default=Path("logs/chroma_logs"))
    parser.add_argument("--persist-dir", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(CHROMA_PERSIST_DIRECTORY) / f"{CHROMA_DATASET_GEOGRAPHIES_COLLECTION_NAME}.manifest.json",
    )
    args = parser.parse_args()

    logger = build_logger(args.log_dir)

    client = chromadb.PersistentClient(
        path=str(args.persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )

    geography_rows: list[GeographyRow] = []
    for category, dataset, year, url in iter_source_pages(DEFAULT_DATASETS):
        try:
            geography_rows.extend(fetch_geographies(category, dataset, year, url, logger))
        except Exception as exc:
            logger.error(
                "FETCH_FAILURE category=%s year=%s url=%s error=%s",
                category,
                year,
                url,
                exc,
            )

    example_rows: list[ExampleRow] = []
    for category, dataset, year, url in iter_example_pages(DEFAULT_DATASETS):
        try:
            example_rows.extend(fetch_examples(category, dataset, year, url, logger))
        except Exception as exc:
            logger.warning(
                "EXAMPLES_FETCH_FAILURE category=%s year=%s url=%s error=%s",
                category,
                year,
                url,
                exc,
            )

    docs = summarize_geography_levels(geography_rows, example_rows)
    logger.info("UPSERT_START docs=%s", len(docs))
    count = upsert_geography_levels(client, docs)
    write_manifest(args.manifest, document_count=count, docs=docs)
    logger.info("UPSERT_DONE docs=%s manifest=%s", count, args.manifest)


if __name__ == "__main__":
    main()
