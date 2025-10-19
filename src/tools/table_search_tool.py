import os
import sys
import logging
from langchain_core.tools import BaseTool
import requests
from pydantic import ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.chroma_utils import initialize_chroma_client, get_chroma_collection_tables


logger = logging.getLogger(__name__)

class TableSearchTool(BaseTool):
    """
    Discover available geography levels and enumerate areas
    """
    name: str = "table_search"
    description: str = """
    Search ChromaDB for Census tables matching a concept.
    Returns table metadata including supported geographies.
    
    Examples:
    - "Find tables about median income"
    - "What tables have population data?"
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, query: str, category: str = None):
        # Search ChromaDB tables collection

        logger.info(f"Running TableSearchTool with query: {query} and category: {category}")
        client = initialize_chroma_client()
        chroma = get_chroma_collection_tables(client)
        

        logger.info(f"Searching ChromaDB for tables matching query: {query} and category: {category}")
        results = chroma.query(
            query_texts=[query],
            n_results=5,
            where={"category": category} if category else None
        )

        logger.info(f"Found {len(results['metadatas'][0])} tables")
        return self._format_results(results)
    

    def _format_results(self, results):
        """Format search results into a list of table dictionaries"""
        return [
            {
                "table_code": metadata.get("table_code", ""),
                "table_name": metadata.get("table_name", ""),
                "description": metadata.get("description", ""),
                "dataset": metadata.get("dataset", ""),
                "data_types": metadata.get("data_types", "").split(",") if metadata.get("data_types") else [],
                "years_available": metadata.get("years_available", "").split(",") if metadata.get("years_available") else [],
                "score": 1.0 - distance
            }
            for metadata, distance in zip(results["metadatas"][0], results["distances"][0])
        ]
