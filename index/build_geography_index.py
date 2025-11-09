"""
Build the census_geography_hierarchies Chroma collection from Census example tables.
"""

from __future__ import annotations

import sys
import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Dict, Iterable, List, Tuple
from dotenv import load_dotenv
import json

import chromadb
import requests
from bs4 import BeautifulSoup, Tag
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_EMBEDDING_MODEL,
    DEFAULT_DATASETS,
)

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
    notes: List[str]


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def build_logger(log_dir: Path) -> logging.Logger:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
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
    datasets: Iterable[Tuple[str, Iterable[int]]],
) -> Iterable[Tuple[str, str, int, str]]:
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
            if dataset.endswith("spp"):
                url = f"https://api.census.gov/data/{year}/{dataset}/geography.html"
            else:
                url = f"https://api.census.gov/data/{year}/{dataset}/examples.html"
            yield category, dataset, year, url


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


def parse_table(
    category: str, dataset: str, year: int, table: Tag, base_url: str
) -> List[ExampleRow]:
    rows = table.find_all("tr")
    if not rows:
        return []

    headers = [
        cell.get_text(" ", strip=True).lower()
        for cell in rows[0].find_all(["th", "td"])
    ]
    notes: List[str] = []
    parsed_rows: List[ExampleRow] = []

    current_hierarchy = ""
    current_level = ""
    for row in rows[1:]:
        cells = [
            extract_cell_text(cell, base_url)
            for cell in row.find_all(["th", "td"])
            if cell.get_text(strip=True)
        ]
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


def fetch_examples(
    category: str, dataset: str, year: int, url: str, logger: logging.Logger
) -> List[ExampleRow]:
    start = monotonic()
    logger.info("FETCH_START category=%s year=%s url=%s", category, year, url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("no table elements found")

    rows: List[ExampleRow] = []
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


def summarize_by_hierarchy(rows: List[ExampleRow]) -> Dict[Tuple[str, int, str], Dict]:
    grouped: Dict[Tuple[str, int, str], Dict] = defaultdict(
        lambda: {"examples": [], "levels": set(), "notes": set()}
    )

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


def build_document(
    hierarchy: str, ordering: List[str], level_code: str, example_url: str
) -> str:
    ordering_clause = " → ".join(ordering) if ordering else "n/a"
    return (
        f"Geography hierarchy: {hierarchy}. "
        f"Ordering: {ordering_clause}. "
        f"Summary level code: {level_code}. "
        f"Example: {example_url}"
    )


def build_metadata(
    dataset: str, year: int, hierarchy: str, level_code: str, examples: List[str]
) -> Dict[str, object]:
    parts = [part.strip() for part in hierarchy.split("›") if part.strip()]
    for_level = parts[-1] if parts else ""
    ordering_list = json.dumps(parts[:-1])
    return {
        "dataset": dataset,
        "table_category": dataset,
        "year": year,
        "geography_hierarchy": hierarchy,
        "geography_level": level_code,
        "for_level": for_level,
        "ordering_list": ordering_list,
        "example_urls": json.dumps(examples),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def upsert_documents(
    client: chromadb.PersistentClient, docs: Dict[Tuple[str, int, str], Dict]
) -> None:
    embedding_function = OpenAIEmbeddingFunction(model_name=CHROMA_EMBEDDING_MODEL)
    collection = client.get_or_create_collection(
        CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME,
        metadata={"description": "Census geography hierarchy ordering examples"},
        embedding_function=embedding_function,
    )

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, object]] = []

    for (dataset, year, hierarchy), payload in docs.items():
        doc_id = f"{dataset}:{year}:{hierarchy}"
        ids.append(doc_id)

        ordering_parts = [part.strip() for part in hierarchy.split("›") if part.strip()]
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build census geography hierarchy vector database."
    )
    parser.add_argument("--log-dir", type=Path, default=Path("logs/chroma_logs"))
    parser.add_argument(
        "--persist-dir", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY)
    )
    args = parser.parse_args()

    logger = build_logger(args.log_dir)

    client = chromadb.PersistentClient(
        path=str(args.persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )

    all_rows: List[ExampleRow] = []
    for category, dataset, year, url in iter_source_pages(DEFAULT_DATASETS):
        try:
            rows = fetch_examples(category, dataset, year, url, logger)
            all_rows.extend(rows)
        except Exception as exc:
            logger.error(
                "FETCH_FAILURE category=%s year=%s url=%s error=%s",
                category,
                year,
                url,
                exc,
            )

    grouped = summarize_by_hierarchy(all_rows)
    logger.info("UPSERT_START docs=%s", len(grouped))
    upsert_documents(client, grouped)
    logger.info("UPSERT_DONE")


if __name__ == "__main__":
    main()
