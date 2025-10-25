"""
Table-Level Chroma Index Builder for Census Groups
Builds a searchable index of Census tables (not individual variables)
"""

import sys
import logging
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb.config import Settings
from typing import Dict
from dotenv import load_dotenv


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION_NAME,
    CHROMA_EMBEDDING_MODEL,
)

from src.utils.census_groups import CensusGroupsAPI

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


class CensusTableIndexBuilder:
    """Build ChromaDB index at table level (not variable level)"""

    def __init__(self):
        self.groups_api = CensusGroupsAPI()
        self.client = None
        self.table_collection = None
        self.base_url = "https://api.census.gov/data"
        self.embedding_function = OpenAIEmbeddingFunction(
            model_name=CHROMA_EMBEDDING_MODEL
        )

    def initialize_chroma(self):
        """Initialize Chroma client and collection"""
        logger.info(f"Initializing Chroma collection: {CHROMA_TABLE_COLLECTION_NAME}")

        # Ensure chroma directory exists
        Path(CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)

        # Initialize Chroma client with persistent storage
        self.client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        try:
            self.collection = self.client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
            logger.info(f"Found existing collection: {CHROMA_TABLE_COLLECTION_NAME}")
        except Exception:
            self.collection = self.client.create_collection(
                name=CHROMA_TABLE_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self.embedding_function,
            )
            logger.info(f"Created new collection: {CHROMA_TABLE_COLLECTION_NAME}")

    # TODO: Build table-level index

    def build_document_text(self, table_info: Dict) -> str:
        """Build searchable document text from variable metadata"""

        parts = [
            table_info.get("table_code", ""),  # B01003
            table_info.get("table_name", ""),  # TOTAL POPULATION
            table_info.get("description", ""),  # (usually same as name)
            " ".join(table_info.get("data_types", [])),  # population demographics
            f"dataset {table_info.get('dataset', '')}",  # dataset acs/acs5
        ]

        # Add years information
        years = table_info.get("years_available", [])
        if years:
            parts.append(f"years {' '.join(map(str, years))}")

        return " ".join(filter(None, parts)).lower()

    def upsert_to_chroma(self, aggregated_vars: Dict[str, Dict], batch_size: int = 100):
        """Upsert aggregated variables to Chroma collection"""
        logger.info(f"Upserting {len(aggregated_vars)} variables to Chroma...")

        # Prepare data for batch upsert
        ids = []
        documents = []
        metadatas = []

        for i, (key, table_info) in enumerate(aggregated_vars.items()):
            # Build document text for semantic search
            document_text = self.build_document_text(table_info)

            # Prepare metadata (Chroma requires string values)
            metadata = {
                "table_code": table_info.get("table_code", ""),  # Not "var"
                "table_name": table_info.get("table_name", ""),  # Not "label"
                "description": table_info.get("description", ""),  # Not "concept"
                "dataset": table_info.get("dataset", ""),
                "category": table_info.get("category", "detail"),
                "uses_groups": table_info.get("uses_groups", False),
                "years_available": ",".join(
                    map(str, table_info.get("years_available", []))
                ),
                "data_types": ",".join(table_info.get("data_types", [])),  # New field
            }

            ids.append(key)
            documents.append(document_text)
            metadatas.append(metadata)

            # Upsert in batches
            if (i + 1) % batch_size == 0 or i == len(aggregated_vars) - 1:
                logger.info(f"Upserting batch {i // batch_size + 1} ({len(ids)} items)")

                try:
                    self.collection.upsert(
                        ids=ids, documents=documents, metadatas=metadatas
                    )
                    logger.info(f"Successfully upserted batch {i // batch_size + 1}")
                except Exception as e:
                    logger.error(f"Error upserting batch: {e}")

                # Reset for next batch
                ids = []
                documents = []
                metadatas = []

    def build_index(self, year: int = 2023):
        """Main method to build the complete index from ALL categories"""

        logger.info("Starting Census TABLE index build (all categories)...")
        logger.info(f"Year: {year}")

        # Initialize Chroma
        self.initialize_chroma()

        # Fetch tables from ALL 5 categories
        logger.info("Fetching tables from ALL 5 categories...")
        all_tables = self.groups_api.aggregate_all_categories(year)

        logger.info(f"Total tables fetched: {len(all_tables)} tables")

        # Count by category
        by_category = {}
        for table_info in all_tables.values():
            cat = table_info.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        logger.info("Tables by category:")
        for cat, count in by_category.items():
            logger.info(f"  {cat}: {count} tables")

        # Upsert to ChromaDB
        self.upsert_to_chroma(all_tables)

        # Verify index
        count = self.collection.count()
        logger.info(f"Index build complete! Total tables indexed: {count}")

        return count


def main():
    """Main entry point for building the index"""
    builder = CensusTableIndexBuilder()

    try:
        # Test 1: Population query
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: Population query (should find Detail table)")
        logger.info("=" * 60)
        test_results = builder.collection.query(
            query_texts=["population total"], n_results=3
        )
        for i, metadata in enumerate(test_results["metadatas"][0]):
            logger.info(
                f"  {i + 1}. {metadata['table_code']} ({metadata['category']}): {metadata['table_name']}"
            )

        # Test 2: Overview query
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Overview query (should find Subject table)")
        logger.info("=" * 60)
        test_results = builder.collection.query(
            query_texts=["demographic overview age sex"], n_results=3
        )
        for i, metadata in enumerate(test_results["metadatas"][0]):
            logger.info(
                f"  {i + 1}. {metadata['table_code']} ({metadata['category']}): {metadata['table_name']}"
            )

        # Test 3: Profile query
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Profile query (should find Profile table)")
        logger.info("=" * 60)
        test_results = builder.collection.query(
            query_texts=["demographic profile housing"], n_results=3
        )
        for i, metadata in enumerate(test_results["metadatas"][0]):
            logger.info(
                f"  {i + 1}. {metadata['table_code']} ({metadata['category']}): {metadata['table_name']}"
            )

    except Exception as e:
        logger.error(f"Index build failed: {e}")
        raise


if __name__ == "__main__":
    main()
