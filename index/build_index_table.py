"""
Table-Level Chroma Index Builder for Census Groups
Builds a searchable index of Census tables (not individual variables)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.types import Metadata
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CATALOG_YEAR_START,
    CENSUS_CATALOG_INDEX_VERSION,
    CENSUS_CATALOG_SCHEMA_VERSION,
    CENSUS_CATEGORIES,
    CHROMA_EMBEDDING_MODEL,
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
    LATEST_AVAILABLE_YEAR,
)
from index.table_metadata import enrich_table_info
from src.domain.census_groups import CensusGroupsAPI
from src.domain.geography_catalog import IndexManifest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
BASE_URL = "https://api.census.gov/data"

load_dotenv()


def stable_table_id(dataset: str, table_code: str) -> str:
    """Return a deterministic ID that cannot collide across Census datasets."""
    return f"table:{dataset}:{table_code}"


def write_table_manifest(
    path: Path,
    *,
    document_count: int,
    tables: dict[str, dict],
) -> IndexManifest:
    """Write the portable build receipt for census_tables beside Chroma."""
    datasets = sorted({str(item.get("dataset", "")) for item in tables.values() if item.get("dataset")})
    years: set[int] = set()
    source_urls: set[str] = set()
    for item in tables.values():
        for year in item.get("years_available", []):
            years.add(int(year))
            dataset = str(item.get("dataset", ""))
            if dataset:
                source_urls.add(f"{BASE_URL}/{int(year)}/{dataset}/groups.json")
    manifest = IndexManifest(
        collection_name=CHROMA_TABLE_COLLECTION_NAME,
        schema_version=CENSUS_CATALOG_SCHEMA_VERSION,
        index_version=CENSUS_CATALOG_INDEX_VERSION,
        document_count=document_count,
        datasets=datasets,
        years=sorted(years),
        source_urls=sorted(source_urls),
        metadata={
            "categories": ",".join(sorted(CENSUS_CATEGORIES)),
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


class CensusTableIndexBuilder:
    """Build ChromaDB index at table level (not variable level)"""

    def __init__(
        self,
        *,
        persist_dir: str | Path = CHROMA_PERSIST_DIRECTORY,
        embedding_function: Any | None = None,
        groups_api: CensusGroupsAPI | None = None,
        client: ClientAPI | None = None,
    ):
        self.persist_dir = Path(persist_dir)
        self.groups_api = groups_api or CensusGroupsAPI()
        self.client = client
        self.collection = None
        self.base_url = BASE_URL
        self.embedding_function = embedding_function or OpenAIEmbeddingFunction(model_name=CHROMA_EMBEDDING_MODEL)

    def initialize_chroma(self, *, delete_existing: bool = True) -> None:
        """Initialize Chroma client and create a clean census_tables collection."""
        logger.info("Initializing Chroma collection: %s at %s", CHROMA_TABLE_COLLECTION_NAME, self.persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        if self.client is None:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )

        if delete_existing:
            try:
                self.client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
                self.client.delete_collection(CHROMA_TABLE_COLLECTION_NAME)
                logger.info("Deleted existing collection: %s", CHROMA_TABLE_COLLECTION_NAME)
            except Exception:
                logger.info("No existing %s collection to delete", CHROMA_TABLE_COLLECTION_NAME)

        built_at = datetime.now(UTC).isoformat()
        self.collection = self.client.create_collection(
            name=CHROMA_TABLE_COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine",
                "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
                "index_version": CENSUS_CATALOG_INDEX_VERSION,
                "built_at": built_at,
            },
            embedding_function=cast(Any, self.embedding_function),
        )
        logger.info("Created collection: %s", CHROMA_TABLE_COLLECTION_NAME)

    def build_document_text(self, table_info: dict) -> str:
        """Build searchable document text from table metadata."""
        phase5 = enrich_table_info(table_info)
        parts = [
            table_info.get("table_code", ""),
            table_info.get("table_name", ""),
            table_info.get("description", ""),
            " ".join(table_info.get("data_types", [])),
            phase5["primary_topic"],
            phase5["breadth"],
            phase5["universe"],
            f"dataset {table_info.get('dataset', '')}",
        ]
        years = table_info.get("years_available", [])
        if years:
            parts.append(f"years {' '.join(map(str, years))}")
        return " ".join(filter(None, parts)).lower()

    def upsert_to_chroma(self, aggregated_vars: dict[str, dict], batch_size: int = 100) -> None:
        """Upsert aggregated tables to the Chroma collection."""
        if self.collection is None:
            raise RuntimeError("collection is not initialized; call initialize_chroma() first")

        logger.info("Upserting %s tables to Chroma...", len(aggregated_vars))
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[Metadata] = []

        for index, table_info in enumerate(aggregated_vars.values()):
            document_text = self.build_document_text(table_info)
            dataset = str(table_info.get("dataset", ""))
            table_code = str(table_info.get("table_code", ""))
            candidate_id = stable_table_id(dataset, table_code)
            years = sorted(int(year) for year in table_info.get("years_available", []))
            if not years:
                raise ValueError(f"table {candidate_id} has no years_available")
            source_year = years[-1]
            data_types = [str(item) for item in table_info.get("data_types", [])]
            phase5 = enrich_table_info(table_info)

            metadata: Metadata = {
                "candidate_id": candidate_id,
                "display_name": str(table_info.get("table_name", "")),
                "table_code": table_code,
                "table_name": str(table_info.get("table_name", "")),
                "description": str(table_info.get("description", "")),
                "dataset": dataset,
                "category": str(table_info.get("category", "detail")),
                "primary_topic": phase5["primary_topic"],
                "breadth": phase5["breadth"],
                "universe": phase5["universe"],
                "uses_groups": bool(table_info.get("uses_groups", False)),
                "year": source_year,
                "years_available": ",".join(map(str, years)),
                "data_types": ",".join(data_types),
                "provenance": "census_groups",
                "source_url": f"{BASE_URL}/{source_year}/{dataset}/groups.json",
                "schema_version": CENSUS_CATALOG_SCHEMA_VERSION,
                "index_version": CENSUS_CATALOG_INDEX_VERSION,
            }

            ids.append(candidate_id)
            documents.append(document_text)
            metadatas.append(metadata)

            if (index + 1) % batch_size == 0 or index == len(aggregated_vars) - 1:
                logger.info("Upserting batch %s (%s items)", (index // batch_size) + 1, len(ids))
                self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                ids = []
                documents = []
                metadatas = []

    def build_index(
        self,
        *,
        year_start: int = CATALOG_YEAR_START,
        year_end: int = LATEST_AVAILABLE_YEAR,
        delete_existing: bool = True,
        manifest_path: Path | None = None,
    ) -> int:
        """Build the complete multi-year table index from all categories."""
        logger.info(
            "Starting Census TABLE index build (all categories) years=%s-%s delete_existing=%s",
            year_start,
            year_end,
            delete_existing,
        )
        self.initialize_chroma(delete_existing=delete_existing)

        all_tables = self.groups_api.aggregate_all_categories_across_years(
            year_start=year_start,
            year_end=year_end,
        )
        logger.info("Total tables fetched: %s", len(all_tables))

        by_category: dict[str, int] = {}
        for table_info in all_tables.values():
            category = str(table_info.get("category", "unknown"))
            by_category[category] = by_category.get(category, 0) + 1
        for category, count in sorted(by_category.items()):
            logger.info("  %s: %s tables", category, count)

        self.upsert_to_chroma(all_tables)
        count = self.collection.count() if self.collection is not None else 0
        path = manifest_path or (self.persist_dir / f"{CHROMA_TABLE_COLLECTION_NAME}.manifest.json")
        write_table_manifest(path, document_count=count, tables=all_tables)
        logger.info("Index build complete! Total tables indexed: %s manifest=%s", count, path)
        return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the census_tables Chroma catalog collection.")
    parser.add_argument("--persist-dir", type=Path, default=Path(CHROMA_PERSIST_DIRECTORY))
    parser.add_argument("--year-start", type=int, default=CATALOG_YEAR_START)
    parser.add_argument("--year-end", type=int, default=LATEST_AVAILABLE_YEAR)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest path (default: <persist-dir>/census_tables.manifest.json)",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not delete census_tables first (unsafe; may leave legacy IDs).",
    )
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()

    if args.year_end < args.year_start:
        raise SystemExit("--year-end must be >= --year-start")

    builder = CensusTableIndexBuilder(persist_dir=args.persist_dir)
    try:
        builder.build_index(
            year_start=args.year_start,
            year_end=args.year_end,
            delete_existing=not args.keep_existing,
            manifest_path=args.manifest,
        )
        if args.skip_smoke or builder.collection is None:
            return
        logger.info("SMOKE: population total")
        test_results = builder.collection.query(query_texts=["population total"], n_results=3)
        for metadata in (test_results.get("metadatas") or [[]])[0]:
            logger.info(
                "  %s (%s): %s",
                metadata.get("table_code"),
                metadata.get("category"),
                metadata.get("table_name"),
            )
    except Exception as exc:
        logger.error("Index build failed: %s", exc)
        raise


if __name__ == "__main__":
    main()
