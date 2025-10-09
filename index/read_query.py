from pathlib import Path
from typing import Dict, List
import chromadb
import logging
import pprint

# Import configuration
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_COLLECTION_NAME


# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ChromaQuery:
    """ChromaQuery class to read a query from the command line and return a list of dictionaries"""

    def __init__(self):
        try:
            logger.info(
                f"Initializing ChromaQuery with collection: {CHROMA_COLLECTION_NAME}"
            )
            if not CHROMA_PERSIST_DIRECTORY:
                raise ValueError("CHROMA_PERSIST_DIRECTORY not configured")

            if not CHROMA_COLLECTION_NAME:
                raise ValueError("CHROMA_COLLECTION_NAME not configured")

            self.client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
            self.collection = self.client.get_collection(CHROMA_COLLECTION_NAME)

        except chromadb.errors.NotFoundError as e:
            logger.error(f"Error initializing ChromaQuery: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing ChromaQuery: {e}")
            raise

    def read_query(
        self, query: str, fallback_empty: bool = True, timeout: int = 30
    ) -> List[Dict]:
        """Read a query from the command line and return a list of dictionaries"""

        try:
            if not query or not isinstance(query, str):
                logger.error("Query is required")
                raise ValueError("Query is required")

            if not query.strip():
                logger.error("Query is required")
                raise ValueError("Query is required")

            results = self.collection.query(
                query_texts=[query],
                n_results=10,
                include=["documents", "metadatas", "distances"],
            )

            return results

        except Exception as e:
            logger.error(f"Error reading query: {e}")
            if fallback_empty:
                logger.info("Returning empty results due to query failure")
                return {"documents": [], "metadatas": [], "distances": []}
            raise


if __name__ == "__main__":
    query = "What's the population of Chicago?"
    chroma_query = ChromaQuery()
    results = chroma_query.read_query(query)
    pprint.pprint(results)
    collection_names = chroma_query.client.list_collections()
    pprint.pprint(collection_names)
