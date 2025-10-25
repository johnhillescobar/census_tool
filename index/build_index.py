"""
Chroma Index Builder for Census Variables
Fetches variables.json from Census API for each dataset/year and builds a searchable index
"""

import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb.config import Settings
from dotenv import load_dotenv
import logging

# Import configuration
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_COLLECTION_NAME,
    CHROMA_EMBEDDING_MODEL,
    DEFAULT_DATASETS,
    CENSUS_API_TIMEOUT,
    CENSUS_API_MAX_RETRIES,
    CENSUS_API_BACKOFF_FACTOR,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


class CensusIndexBuilder:
    """Builds and maintains Chroma index of Census variables"""

    def __init__(self):
        self.base_url = "https://api.census.gov/data"
        self.client = None
        self.collection = None
        self.embedding_function = OpenAIEmbeddingFunction(
            model_name=CHROMA_EMBEDDING_MODEL
        )

    def initialize_chroma(self):
        """Initialize Chroma client and collection"""
        logger.info(f"Initializing Chroma collection: {CHROMA_COLLECTION_NAME}")

        # Ensure chroma directory exists
        Path(CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)

        # Initialize Chroma client with persistent storage
        self.client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        try:
            self.collection = self.client.get_collection(CHROMA_COLLECTION_NAME)
            logger.info(f"Found existing collection: {CHROMA_COLLECTION_NAME}")
        except Exception:
            self.collection = self.client.create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self.embedding_function,
            )
            logger.info(f"Created new collection: {CHROMA_COLLECTION_NAME}")

    def fetch_variables_json(self, dataset: str, year: int) -> Dict:
        """Fetch variables.json for a specific dataset and year"""
        url = f"{self.base_url}/{year}/{dataset}/variables.json"

        for attempt in range(CENSUS_API_MAX_RETRIES):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1})")
                response = requests.get(url, timeout=CENSUS_API_TIMEOUT)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < CENSUS_API_MAX_RETRIES - 1:
                    wait_time = CENSUS_API_BACKOFF_FACTOR * (2**attempt)
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to fetch {url} after {CENSUS_API_MAX_RETRIES} attempts"
                    )
                    raise

    def aggregate_variables(
        self, datasets: List[Tuple[str, List[int]]]
    ) -> Dict[str, Dict]:
        """Aggregate variables across years for each dataset"""
        logger.info("Starting variable aggregation...")

        aggregated = defaultdict(
            lambda: {
                "var": "",
                "label": "",
                "concept": "",
                "universe": "",
                "dataset": "",
                "years_available": set(),
            }
        )

        for dataset, years in datasets:
            logger.info(f"Processing dataset: {dataset} for years {years}")

            for year in years:
                try:
                    variables_data = self.fetch_variables_json(dataset, year)

                    # Process variables from the JSON response
                    if "variables" in variables_data:
                        for var_code, var_info in variables_data["variables"].items():
                            key = f"{dataset}:{var_code}"

                            # Update aggregated info
                            aggregated[key]["var"] = var_code
                            aggregated[key]["label"] = var_info.get("label", "")
                            aggregated[key]["concept"] = var_info.get("concept", "")
                            aggregated[key]["universe"] = var_info.get("universe", "")
                            aggregated[key]["dataset"] = dataset
                            aggregated[key]["years_available"].add(year)

                    # Polite pacing between requests
                    time.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error processing {dataset} {year}: {e}")
                    continue

        # Convert years_available sets to sorted lists
        for key, var_info in aggregated.items():
            var_info["years_available"] = sorted(list(var_info["years_available"]))

        logger.info(f"Aggregated {len(aggregated)} unique variables")
        return dict(aggregated)

    def build_document_text(self, var_info: Dict) -> str:
        """Build searchable document text from variable metadata"""
        parts = [
            var_info.get("label", ""),
            var_info.get("concept", ""),
            var_info.get("universe", ""),
            f"dataset {var_info.get('dataset', '')}",
            f"variable {var_info.get('var', '')}",
        ]

        # Add years information
        years = var_info.get("years_available", [])
        if years:
            parts.append(f"years {' '.join(map(str, years))}")

        return " ".join(filter(None, parts))

    def upsert_to_chroma(self, aggregated_vars: Dict[str, Dict], batch_size: int = 100):
        """Upsert aggregated variables to Chroma collection"""
        logger.info(f"Upserting {len(aggregated_vars)} variables to Chroma...")

        # Prepare data for batch upsert
        ids = []
        documents = []
        metadatas = []

        for i, (key, var_info) in enumerate(aggregated_vars.items()):
            # Build document text for semantic search
            document_text = self.build_document_text(var_info)

            # Prepare metadata (Chroma requires string values)
            metadata = {
                "var": var_info.get("var", ""),
                "label": var_info.get("label", ""),
                "concept": var_info.get("concept", ""),
                "universe": var_info.get("universe", ""),
                "dataset": var_info.get("dataset", ""),
                "years_available": ",".join(
                    map(str, var_info.get("years_available", []))
                ),
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

    def build_index(self, datasets: List[Tuple[str, List[int]]] = None):
        """Main method to build the complete index"""
        if datasets is None:
            datasets = DEFAULT_DATASETS

        logger.info("Starting Census variable index build...")
        logger.info(f"Datasets to process: {datasets}")

        # Initialize Chroma
        self.initialize_chroma()

        # Aggregate variables across years
        aggregated_vars = self.aggregate_variables(datasets)

        if not aggregated_vars:
            logger.error("No variables found to index!")
            return

        # Upsert to Chroma
        self.upsert_to_chroma(aggregated_vars)

        # Verify index
        count = self.collection.count()
        logger.info(f"Index build complete! Total variables indexed: {count}")

        # Show some sample results
        sample_results = self.collection.get(limit=3)
        logger.info("Sample indexed variables:")
        for i, (var, label, dataset) in enumerate(
            zip(
                sample_results["metadatas"][0]["var"],
                sample_results["metadatas"][0]["label"],
                sample_results["metadatas"][0]["dataset"],
            )
        ):
            logger.info(f"  {i + 1}. {var}: {label} ({dataset})")


def main():
    """Main entry point for building the index"""
    builder = CensusIndexBuilder()

    try:
        # Build index with default datasets
        builder.build_index()

        # Optional: Test retrieval
        logger.info("Testing retrieval...")
        test_results = builder.collection.query(
            query_texts=["population total"], n_results=3
        )

        logger.info("Test query 'population total' results:")
        for i, (var, label) in enumerate(
            zip(test_results["metadatas"][0], test_results["documents"][0])
        ):
            logger.info(f"  {i + 1}. {var['var']}: {var['label']}")

    except Exception as e:
        logger.error(f"Index build failed: {e}")
        raise


if __name__ == "__main__":
    main()
