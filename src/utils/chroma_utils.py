"""
Chroma database utilities for Census variable retrieval
"""

import chromadb
from chromadb.config import Settings
import logging
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_COLLECTION_NAME, CHROMA_TABLE_COLLECTION_NAME

logger = logging.getLogger(__name__)


def initialize_chroma_client() -> chromadb.PersistentClient:
    """Initialize and return Chroma client"""
    try:
        client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
        )

    except Exception as e:
        logger.error(f"Failed to connect to Chroma: {e}")
        return {
            "error": f"Failed to connect to variable database: {e}",
            "logs": ["retrieve: ERROR - Chroma connection failed"],
        }

    return client


def get_chroma_collection_variables(client: chromadb.PersistentClient) -> chromadb.Collection:
    """Get the census variables collection"""
    # Implementation here
    try:
        collection = client.get_collection(CHROMA_COLLECTION_NAME)
    except Exception as e:
        logger.error(f"Failed to get Chroma collection: {e}")
        return {
            "error": f"Failed to get Chroma collection: {e}",
            "logs": ["retrieve: ERROR - Chroma collection not found"],
        }
    return collection


def get_chroma_collection_tables(client: chromadb.PersistentClient) -> chromadb.Collection:
    """Get the census tables collection"""
    try:
        collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
    except Exception as e:
        logger.error(f"Failed to get Chroma collection: {e}")
        return {
            "error": f"Failed to get Chroma collection: {e}",
            "logs": ["retrieve: ERROR - Chroma collection not found"],
        }
    return collection