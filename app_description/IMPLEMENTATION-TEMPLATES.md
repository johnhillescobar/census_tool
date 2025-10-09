# Implementation Templates & Code Examples

## Purpose
This document provides ready-to-use code templates and implementation examples for Phase 8 and Phase 9 remediation work. Copy and adapt these templates as needed.

---

## PHASE 8 Templates: Table-Level Architecture

### Template 1: Updated Config for Table-Level Collections

```python
# config.py - Add these configurations

# Chroma Settings - Update for table-level collections
CHROMA_PERSIST_DIRECTORY = "./chroma"
CHROMA_TABLE_COLLECTION = "census_tables"  # NEW: Table-level collection
CHROMA_VARIABLE_COLLECTION = "census_variables"  # Keep for refinement
CHROMA_EMBEDDING_MODEL = "text-embedding-3-large"

# Table Index Settings
TABLE_INDEX_CONFIG = {
    "primary_collection": "census_tables",
    "secondary_collection": "census_variables",
    "search_strategy": "hierarchical",  # table-first, then variables
    "table_confidence_threshold": 0.6,
    "variable_confidence_threshold": 0.4,
}

# Census Table Metadata
KNOWN_TABLES = {
    "B01003": {
        "name": "Total Population",
        "category": "demographics",
        "primary_var": "B01003_001E",
        "keywords": ["population", "total", "people", "residents"]
    },
    "B19013": {
        "name": "Median Household Income",
        "category": "economics",
        "primary_var": "B19013_001E",
        "keywords": ["income", "median", "household", "earnings"]
    },
    # Add more as you discover them
}
```

### Template 2: Groups API Fetcher

```python
# src/utils/census_groups_api.py - NEW FILE

import requests
import logging
from typing import Dict, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class CensusGroupsAPI:
    """Fetch Census table groups and metadata"""
    
    def __init__(self):
        self.base_url = "https://api.census.gov/data"
        self.timeout = 30
        self.max_retries = 3
    
    @lru_cache(maxsize=100)
    def fetch_groups(self, dataset: str, year: int) -> Optional[Dict]:
        """
        Fetch groups.json for a dataset/year
        
        Args:
            dataset: e.g., "acs/acs5", "acs/acs5/subject"
            year: e.g., 2023
        
        Returns:
            Dict with groups list or None if failed
        
        Example:
            api = CensusGroupsAPI()
            groups = api.fetch_groups("acs/acs5", 2023)
        """
        url = f"{self.base_url}/{year}/{dataset}/groups.json"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch groups from {url}: {e}")
            return None
    
    @lru_cache(maxsize=500)
    def fetch_group_variables(
        self, dataset: str, year: int, group_code: str
    ) -> Optional[Dict]:
        """
        Fetch detailed variables for a specific group
        
        Args:
            dataset: e.g., "acs/acs5"
            year: e.g., 2023
            group_code: e.g., "B01003"
        
        Returns:
            Dict with variable details or None if failed
        
        Example:
            api = CensusGroupsAPI()
            vars = api.fetch_group_variables("acs/acs5", 2023, "B01003")
        """
        url = f"{self.base_url}/{year}/{dataset}/groups/{group_code}.json"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch group variables from {url}: {e}")
            return None
    
    def extract_table_metadata(self, groups_data: Dict) -> List[Dict]:
        """
        Extract structured table metadata from groups.json
        
        Args:
            groups_data: Response from fetch_groups()
        
        Returns:
            List of table metadata dicts
        """
        tables = []
        
        for group in groups_data.get("groups", []):
            table = {
                "code": group.get("name", ""),
                "description": group.get("description", ""),
                "universe": group.get("universe", ""),
                "variables_url": group.get("variables", "")
            }
            tables.append(table)
        
        return tables
    
    def get_primary_variable(self, group_vars: Dict) -> Optional[str]:
        """
        Identify the primary/total variable in a group
        Usually ends in _001E
        
        Args:
            group_vars: Response from fetch_group_variables()
        
        Returns:
            Primary variable code or None
        """
        variables = group_vars.get("variables", {})
        
        # Look for _001E (typically the total/primary variable)
        for var_code in variables:
            if var_code.endswith("_001E"):
                return var_code
        
        # Fallback: return first variable
        if variables:
            return next(iter(variables.keys()))
        
        return None


# Example usage
if __name__ == "__main__":
    api = CensusGroupsAPI()
    
    # Test fetching groups
    groups = api.fetch_groups("acs/acs5", 2023)
    if groups:
        print(f"Found {len(groups.get('groups', []))} tables")
        
        # Test fetching a specific group's variables
        vars = api.fetch_group_variables("acs/acs5", 2023, "B01003")
        if vars:
            primary = api.get_primary_variable(vars)
            print(f"Primary variable for B01003: {primary}")
```

### Template 3: Table-Level Index Builder

```python
# index/build_index_tables.py - NEW FILE (or replace build_index.py)

import logging
from pathlib import Path
import chromadb
from chromadb.config import Settings
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION,
    DEFAULT_DATASETS,
)
from src.utils.census_groups_api import CensusGroupsAPI

logger = logging.getLogger(__name__)


class CensusTableIndexBuilder:
    """Build ChromaDB index at table level (not variable level)"""
    
    def __init__(self):
        self.groups_api = CensusGroupsAPI()
        self.client = None
        self.table_collection = None
    
    def initialize_chroma(self):
        """Initialize ChromaDB with table-level collection"""
        logger.info(f"Initializing table collection: {CHROMA_TABLE_COLLECTION}")
        
        Path(CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIRECTORY,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create or get table collection
        try:
            self.table_collection = self.client.get_collection(CHROMA_TABLE_COLLECTION)
            logger.info(f"Found existing collection: {CHROMA_TABLE_COLLECTION}")
        except:
            self.table_collection = self.client.create_collection(
                name=CHROMA_TABLE_COLLECTION,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {CHROMA_TABLE_COLLECTION}")
    
    def build_table_document(self, table_meta: Dict) -> str:
        """
        Build searchable document text for a Census table
        
        This is what ChromaDB will search against for semantic matching
        """
        parts = [
            table_meta.get("description", ""),
            table_meta.get("universe", ""),
            f"table {table_meta.get('code', '')}",
            f"group {table_meta.get('code', '')}",
        ]
        
        # Add keywords if available
        keywords = table_meta.get("keywords", [])
        if keywords:
            parts.append(" ".join(keywords))
        
        return " ".join(filter(None, parts))
    
    def aggregate_tables(self, datasets: List[Tuple[str, List[int]]]) -> Dict[str, Dict]:
        """
        Aggregate table metadata across years
        
        Returns:
            Dict mapping table codes to metadata
        """
        tables = {}
        
        for dataset, years in datasets:
            logger.info(f"Processing dataset: {dataset}")
            
            for year in years:
                try:
                    # Fetch groups for this dataset/year
                    groups_data = self.groups_api.fetch_groups(dataset, year)
                    
                    if not groups_data:
                        logger.warning(f"No groups data for {dataset} {year}")
                        continue
                    
                    # Process each table/group
                    for group in groups_data.get("groups", []):
                        table_code = group.get("name", "")
                        
                        if not table_code:
                            continue
                        
                        # Initialize or update table entry
                        if table_code not in tables:
                            tables[table_code] = {
                                "code": table_code,
                                "description": group.get("description", ""),
                                "universe": group.get("universe", ""),
                                "dataset": dataset,
                                "years_available": set(),
                                "variables_url": group.get("variables", "")
                            }
                        
                        # Add this year to availability
                        tables[table_code]["years_available"].add(year)
                    
                    logger.info(f"Processed {dataset} {year}")
                    
                except Exception as e:
                    logger.error(f"Error processing {dataset} {year}: {e}")
                    continue
        
        # Convert sets to sorted lists
        for table_code in tables:
            tables[table_code]["years_available"] = sorted(
                list(tables[table_code]["years_available"])
            )
        
        logger.info(f"Aggregated {len(tables)} unique tables")
        return tables
    
    def upsert_tables_to_chroma(self, tables: Dict[str, Dict], batch_size: int = 50):
        """Upsert table metadata to ChromaDB"""
        logger.info(f"Upserting {len(tables)} tables to ChromaDB...")
        
        ids = []
        documents = []
        metadatas = []
        
        for i, (code, table_meta) in enumerate(tables.items()):
            # Build searchable document
            doc_text = self.build_table_document(table_meta)
            
            # Prepare metadata (must be strings for ChromaDB)
            metadata = {
                "code": table_meta["code"],
                "description": table_meta["description"],
                "universe": table_meta["universe"],
                "dataset": table_meta["dataset"],
                "years_available": ",".join(map(str, table_meta["years_available"]))
            }
            
            ids.append(f"{table_meta['dataset']}:{code}")
            documents.append(doc_text)
            metadatas.append(metadata)
            
            # Batch upsert
            if (i + 1) % batch_size == 0 or i == len(tables) - 1:
                logger.info(f"Upserting batch {i // batch_size + 1}")
                
                try:
                    self.table_collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                except Exception as e:
                    logger.error(f"Error upserting batch: {e}")
                
                # Reset for next batch
                ids = []
                documents = []
                metadatas = []
    
    def build_index(self, datasets: List[Tuple[str, List[int]]] = None):
        """Main method to build table-level index"""
        if datasets is None:
            datasets = DEFAULT_DATASETS
        
        logger.info("Starting table-level index build...")
        
        # Initialize ChromaDB
        self.initialize_chroma()
        
        # Aggregate tables across years
        tables = self.aggregate_tables(datasets)
        
        if not tables:
            logger.error("No tables found to index!")
            return
        
        # Upsert to ChromaDB
        self.upsert_tables_to_chroma(tables)
        
        # Verify
        count = self.table_collection.count()
        logger.info(f"Index build complete! Total tables indexed: {count}")
        
        # Test query
        test_results = self.table_collection.query(
            query_texts=["total population"],
            n_results=3
        )
        
        logger.info("Test query 'total population' results:")
        for meta in test_results["metadatas"][0]:
            logger.info(f"  - {meta['code']}: {meta['description']}")


def main():
    """Entry point for building table-level index"""
    logging.basicConfig(level=logging.INFO)
    
    builder = CensusTableIndexBuilder()
    
    try:
        builder.build_index()
    except Exception as e:
        logger.error(f"Index build failed: {e}")
        raise


if __name__ == "__main__":
    main()
```

### Template 4: Updated Retrieval Node

```python
# src/nodes/retrieve.py - UPDATE this file

from typing import Dict, Any
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig
import chromadb
import logging

from config import (
    CHROMA_PERSIST_DIRECTORY,
    CHROMA_TABLE_COLLECTION,
    TABLE_INDEX_CONFIG,
)

logger = logging.getLogger(__name__)


def retrieve_node_table_level(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Retrieve Census tables (not variables) based on user intent
    
    This is a 2-stage process:
    1. Find relevant tables using semantic search
    2. Select appropriate variables within chosen tables
    """
    
    intent = state.intent or {}
    
    if not intent:
        return {
            "error": "No intent found",
            "logs": ["retrieve: ERROR - no intent"]
        }
    
    # Stage 1: Find relevant tables
    measures = intent.get("measures", [])
    if not measures:
        return {
            "error": "No measures to search for",
            "logs": ["retrieve: ERROR - no measures"]
        }
    
    # Build table-level query
    query_text = build_table_query(intent)
    logger.info(f"Searching for tables with query: {query_text}")
    
    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    table_collection = client.get_collection(CHROMA_TABLE_COLLECTION)
    
    # Search for tables
    results = table_collection.query(
        query_texts=[query_text],
        n_results=5,
        include=["documents", "metadatas", "distances"]
    )
    
    if not results or not results["metadatas"][0]:
        logger.warning("No tables found")
        return {
            "candidates": [],
            "logs": ["retrieve: no tables found"]
        }
    
    # Stage 2: Process table results and select variables
    candidates = []
    
    for i, metadata in enumerate(results["metadatas"][0]):
        table_code = metadata["code"]
        description = metadata["description"]
        distance = results["distances"][0][i]
        confidence = 1 - distance  # Convert distance to confidence
        
        # Skip if confidence too low
        if confidence < TABLE_INDEX_CONFIG["table_confidence_threshold"]:
            continue
        
        # Determine primary variable for this table
        primary_var = determine_primary_variable(table_code, intent)
        
        if not primary_var:
            logger.warning(f"Could not determine variable for table {table_code}")
            continue
        
        candidate = {
            "var": primary_var,
            "table": table_code,
            "label": description,
            "concept": description,
            "dataset": metadata.get("dataset", "acs/acs5"),
            "confidence": confidence,
            "years_available": metadata.get("years_available", "").split(",")
        }
        
        candidates.append(candidate)
    
    logger.info(f"Found {len(candidates)} table candidates")
    
    return {
        "candidates": candidates,
        "logs": [f"retrieve: found {len(candidates)} tables"]
    }


def build_table_query(intent: Dict[str, Any]) -> str:
    """
    Build table-level search query from user intent
    
    Example:
        measures=["population"] → "total population people demographics"
        measures=["income"] → "median household income earnings economics"
    """
    measures = intent.get("measures", [])
    
    # Map measures to table-level search terms
    measure_to_terms = {
        "population": "total population people residents demographics",
        "median_income": "median household income earnings economics",
        "income": "income earnings household median",
        "housing": "housing units occupied tenure homeownership",
        "education": "education attainment school college degree",
        "employment": "employment unemployment labor force working",
        "poverty": "poverty income below poverty level",
        "race": "race ethnicity demographic characteristics",
        "hispanic": "hispanic latino ethnicity race",
    }
    
    query_parts = []
    for measure in measures:
        terms = measure_to_terms.get(measure.lower(), measure)
        query_parts.append(terms)
    
    return " ".join(query_parts)


def determine_primary_variable(table_code: str, intent: Dict[str, Any]) -> str:
    """
    Determine the primary variable code for a table
    
    Simple approach: Most tables have a primary variable that ends in _001E
    More sophisticated: Look up variable details from groups API
    
    Args:
        table_code: e.g., "B01003"
        intent: User intent with measures
    
    Returns:
        Variable code like "B01003_001E"
    """
    # Simple approach: primary variable is usually {table}_001E
    primary_var = f"{table_code}_001E"
    
    # TODO: For more accuracy, fetch actual variables from groups API
    # and select based on intent measures
    
    return primary_var


# Keep backward compatibility
def retrieve_node(state: CensusState, config: RunnableConfig) -> Dict[str, Any]:
    """Wrapper for backward compatibility"""
    return retrieve_node_table_level(state, config)
```

---

## PHASE 9 Templates: Multi-Category Support

### Template 5: Multi-Category Configuration

```python
# config.py - Add these for Phase 9

# Census Data Categories
CENSUS_CATEGORIES = {
    "detail": {
        "path": "acs/acs5",
        "path_template": "{year}/acs/acs5",
        "prefix": ["B", "C"],
        "description": "Detail Tables - Detailed demographic and housing data",
        "use_cases": ["detailed breakdowns", "granular data", "specific demographics"],
        "priority": 1,  # Default category
        "years_available": list(range(2012, 2024)),
    },
    "subject": {
        "path": "acs/acs5/subject",
        "path_template": "{year}/acs/acs5/subject",
        "prefix": ["S"],
        "description": "Subject Tables - Topic-specific summary data",
        "use_cases": ["overview", "summary", "topic overview"],
        "priority": 2,
        "years_available": list(range(2012, 2024)),
    },
    "profile": {
        "path": "acs/acs1/profile",
        "path_template": "{year}/acs/acs1/profile",
        "prefix": ["DP"],
        "description": "Data Profiles - Comprehensive demographic profiles",
        "use_cases": ["profile", "comprehensive", "all demographics"],
        "priority": 3,
        "years_available": list(range(2012, 2024)),
    },
    "cprofile": {
        "path": "acs/acs5/cprofile",
        "path_template": "{year}/acs/acs5/cprofile",
        "prefix": ["CP"],
        "description": "Comparison Profiles - Multi-year comparisons",
        "use_cases": ["comparison", "change over time", "trends"],
        "priority": 4,
        "years_available": list(range(2012, 2024)),
    },
    "spp": {
        "path": "acs/acs1/spp",
        "path_template": "{year}/acs/acs1/spp",
        "prefix": ["S0201"],
        "description": "Selected Population Profiles - Race/ethnicity specific",
        "use_cases": ["hispanic", "latino", "asian", "race", "ethnicity"],
        "priority": 5,
        "years_available": list(range(2012, 2024)),
    },
}

# Category Selection Keywords
CATEGORY_KEYWORDS = {
    "subject": ["overview", "summary", "all", "comprehensive", "topic"],
    "profile": ["profile", "demographic profile", "full demographics", "complete"],
    "cprofile": ["compare", "comparison", "change", "trend over time", "versus"],
    "spp": ["hispanic", "latino", "latina", "asian", "race", "ethnicity", "racial"],
}

# Fallback Chain
CATEGORY_FALLBACK_CHAIN = ["subject", "detail", "profile", "cprofile"]
```

### Template 6: Category Selector

```python
# src/utils/category_selector.py - NEW FILE

import logging
from typing import Dict, Any, Optional, Tuple
from config import CENSUS_CATEGORIES, CATEGORY_KEYWORDS, CATEGORY_FALLBACK_CHAIN

logger = logging.getLogger(__name__)


class CategorySelector:
    """Select appropriate Census data category based on user intent"""
    
    def __init__(self):
        self.categories = CENSUS_CATEGORIES
        self.keywords = CATEGORY_KEYWORDS
        self.fallback_chain = CATEGORY_FALLBACK_CHAIN
    
    def select_category(
        self, 
        intent: Dict[str, Any],
        geo_level: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Select best category for this query
        
        Args:
            intent: User intent with measures, original_text, etc.
            geo_level: Geography level (some categories limited by geography)
        
        Returns:
            Tuple of (category_name, confidence)
        
        Example:
            selector = CategorySelector()
            category, conf = selector.select_category(
                {"measures": ["population"], "original_text": "give me an overview"}
            )
            # Returns: ("subject", 0.85)
        """
        
        text = intent.get("original_text", "").lower()
        measures = intent.get("measures", [])
        
        # Check for explicit category keywords in text
        for category, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword in text:
                    logger.info(f"Selected category '{category}' based on keyword '{keyword}'")
                    return category, 0.85
        
        # Check measures for race/ethnicity (SPP)
        race_ethnicity_measures = {"hispanic", "latino", "asian", "race", "ethnicity"}
        if any(m.lower() in race_ethnicity_measures for m in measures):
            logger.info("Selected 'spp' category based on race/ethnicity measures")
            return "spp", 0.80
        
        # Check for comparison/trends (cprofile)
        if intent.get("answer_type") == "series":
            time_info = intent.get("time", {})
            if time_info.get("start") and time_info.get("end"):
                logger.info("Selected 'cprofile' for multi-year series")
                return "cprofile", 0.75
        
        # Default to detail tables
        logger.info("Defaulting to 'detail' category")
        return "detail", 0.70
    
    def validate_category_compatibility(
        self,
        category: str,
        geo_level: str,
        year: int
    ) -> Tuple[bool, str]:
        """
        Check if category is compatible with geography and year
        
        Returns:
            (is_valid, error_message)
        """
        cat_config = self.categories.get(category, {})
        
        # Check year availability
        years_available = cat_config.get("years_available", [])
        if year not in years_available:
            return False, f"Category '{category}' not available for year {year}"
        
        # Check geography compatibility (some categories have limitations)
        # For now, assume all compatible
        # TODO: Add specific geography restrictions if discovered
        
        return True, ""
    
    def get_fallback_category(self, failed_category: str) -> Optional[str]:
        """
        Get next fallback category if primary fails
        
        Args:
            failed_category: Category that failed
        
        Returns:
            Next category to try or None
        """
        try:
            idx = self.fallback_chain.index(failed_category)
            if idx < len(self.fallback_chain) - 1:
                next_cat = self.fallback_chain[idx + 1]
                logger.info(f"Falling back from '{failed_category}' to '{next_cat}'")
                return next_cat
        except ValueError:
            pass
        
        # If failed category not in chain, try first in chain
        if self.fallback_chain:
            return self.fallback_chain[0]
        
        return None


# Example usage
if __name__ == "__main__":
    selector = CategorySelector()
    
    # Test cases
    test_intents = [
        {
            "original_text": "Give me an overview of demographics",
            "measures": ["population"],
        },
        {
            "original_text": "What's the Hispanic population?",
            "measures": ["hispanic", "population"],
        },
        {
            "original_text": "Compare income from 2015 to 2020",
            "measures": ["income"],
            "answer_type": "series",
            "time": {"start": 2015, "end": 2020}
        },
    ]
    
    for intent in test_intents:
        category, confidence = selector.select_category(intent)
        print(f"Query: {intent['original_text']}")
        print(f"  → Category: {category} (confidence: {confidence})")
        print()
```

### Template 7: Dynamic API URL Builder

```python
# src/utils/census_api_utils.py - UPDATE build_census_url function

def build_census_url_dynamic(
    dataset: str,
    year: int,
    variables: List[str] = None,
    groups: List[str] = None,
    geo: Dict[str, Any] = None,
    category: str = "detail"  # NEW parameter
) -> str:
    """
    Build Census API URL with support for all categories
    
    Args:
        dataset: Base dataset (for backward compatibility)
        year: Year for data
        variables: List of variable codes (traditional approach)
        groups: List of group codes for group() calls (NEW)
        geo: Geography filters
        category: Data category (detail, subject, profile, cprofile, spp)
    
    Returns:
        Complete API URL
    
    Examples:
        # Detail table
        build_census_url_dynamic("acs/acs5", 2023, ["B01003_001E"], geo=geo_filters)
        → https://api.census.gov/data/2023/acs/acs5?get=B01003_001E&for=state:06
        
        # Subject table with group()
        build_census_url_dynamic("acs/acs5", 2023, groups=["S0101"], geo=geo_filters, category="subject")
        → https://api.census.gov/data/2023/acs/acs5/subject?get=group(S0101)&for=state:06
        
        # Profile table
        build_census_url_dynamic("acs/acs1", 2023, groups=["DP05"], category="profile")
        → https://api.census.gov/data/2023/acs/acs1/profile?get=group(DP05)&for=us:1
    """
    from config import CENSUS_CATEGORIES
    
    base_url = "https://api.census.gov/data"
    
    # Get category configuration
    cat_config = CENSUS_CATEGORIES.get(category, {})
    
    if cat_config:
        # Use category path template
        path_template = cat_config.get("path_template", "")
        dataset_path = path_template.format(year=year)
    else:
        # Fallback to simple path
        dataset_path = f"{year}/{dataset}"
    
    url = f"{base_url}/{dataset_path}"
    
    # Build get parameter
    if groups:
        # Use group() function for batch retrieval
        get_params = [f"group({group})" for group in groups]
        get_str = ",".join(get_params)
    elif variables:
        # Traditional variable list
        get_str = ",".join(variables)
    else:
        raise ValueError("Must provide either variables or groups")
    
    # Build geography filters
    geo_filters = []
    if geo and geo.get("filters"):
        for key, value in geo["filters"].items():
            geo_filters.append(f"{key}={value}")
    
    # Combine parameters
    params = [f"get={get_str}"] + geo_filters
    param_string = "&".join(params)
    
    return f"{url}?{param_string}"


# Update existing fetch function to use dynamic builder
def fetch_census_data_with_category(
    dataset: str,
    category: str,
    year: int,
    variables: List[str] = None,
    groups: List[str] = None,
    geo: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Fetch Census data with category support
    
    This wraps the existing fetch logic but uses dynamic URL building
    """
    url = build_census_url_dynamic(
        dataset=dataset,
        year=year,
        variables=variables,
        groups=groups,
        geo=geo,
        category=category
    )
    
    # Use existing retry logic
    for attempt in range(CENSUS_API_MAX_RETRIES):
        try:
            response = requests.get(url, timeout=CENSUS_API_TIMEOUT)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "url": url,
                    "category": category,
                    "attempt": attempt + 1,
                }
            
            # ... rest of existing error handling ...
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {str(e)}")
            # ... rest of existing retry logic ...
    
    return {
        "success": False,
        "error": "Max retries exceeded",
        "url": url,
        "attempt": CENSUS_API_MAX_RETRIES,
    }
```

### Template 8: Updated State Types

```python
# src/state/types.py - ADD category field to QuerySpec

from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class QuerySpec(BaseModel):
    dataset: str
    category: str = "detail"  # NEW: detail, subject, profile, cprofile, spp
    year: int
    variables: List[str] = []
    groups: Optional[List[str]] = None  # NEW: For group() API calls
    geo: Dict[str, Any]
    save_as: str
    
    # Optional metadata
    table_code: Optional[str] = None  # NEW: Table code (B01003, S0101, etc.)
    confidence: Optional[float] = None
```

---

## Testing Templates

### Template 9: Phase 8 Test Cases

```python
# test_table_retrieval.py - NEW TEST FILE

import pytest
from src.nodes.retrieve import retrieve_node_table_level
from src.state.types import CensusState

def test_population_query_finds_B01003():
    """Test that 'population' query finds B01003 table"""
    state = CensusState(
        messages=[],
        intent={
            "measures": ["population"],
            "original_text": "What's the population?"
        }
    )
    
    result = retrieve_node_table_level(state, None)
    
    assert len(result["candidates"]) > 0
    
    # First candidate should be B01003 or similar
    top_candidate = result["candidates"][0]
    assert "B01003" in top_candidate["table"]
    assert top_candidate["confidence"] > 0.7

def test_income_query_finds_B19013():
    """Test that 'income' query finds B19013 table"""
    state = CensusState(
        messages=[],
        intent={
            "measures": ["median_income"],
            "original_text": "Show me median income"
        }
    )
    
    result = retrieve_node_table_level(state, None)
    
    assert len(result["candidates"]) > 0
    top_candidate = result["candidates"][0]
    assert "B19013" in top_candidate["table"]

def test_semantic_matching():
    """Test that semantic matching works for 'people living in'"""
    state = CensusState(
        messages=[],
        intent={
            "measures": ["population"],
            "original_text": "How many people live in NYC?"
        }
    )
    
    result = retrieve_node_table_level(state, None)
    
    # Should find population table even with natural language
    assert len(result["candidates"]) > 0
    assert any("B01003" in c["table"] for c in result["candidates"])
```

### Template 10: Phase 9 Test Cases

```python
# test_category_selection.py - NEW TEST FILE

import pytest
from src.utils.category_selector import CategorySelector

def test_overview_selects_subject():
    """Test that 'overview' keyword selects subject tables"""
    selector = CategorySelector()
    
    intent = {
        "original_text": "Give me a demographic overview of California",
        "measures": ["demographics"]
    }
    
    category, confidence = selector.select_category(intent)
    
    assert category == "subject"
    assert confidence > 0.7

def test_hispanic_selects_spp():
    """Test that Hispanic queries select SPP category"""
    selector = CategorySelector()
    
    intent = {
        "original_text": "What's the Hispanic population?",
        "measures": ["hispanic", "population"]
    }
    
    category, confidence = selector.select_category(intent)
    
    assert category == "spp"

def test_url_building_for_subject():
    """Test URL building for subject tables"""
    from src.utils.census_api_utils import build_census_url_dynamic
    
    url = build_census_url_dynamic(
        dataset="acs/acs5",
        year=2023,
        groups=["S0101"],
        geo={"filters": {"for": "state:06"}},
        category="subject"
    )
    
    assert "acs/acs5/subject" in url
    assert "group(S0101)" in url
    assert "state:06" in url

def test_category_fallback():
    """Test fallback chain when category fails"""
    selector = CategorySelector()
    
    next_cat = selector.get_fallback_category("subject")
    assert next_cat == "detail"
    
    next_cat = selector.get_fallback_category("detail")
    assert next_cat == "profile"
```

---

## Usage Examples

### Example 1: Using Groups API

```python
# Fetch and explore Census groups

from src.utils.census_groups_api import CensusGroupsAPI

api = CensusGroupsAPI()

# Get all tables for ACS 5-year 2023
groups = api.fetch_groups("acs/acs5", 2023)

print(f"Found {len(groups['groups'])} tables")

# Look for population tables
for group in groups['groups']:
    if 'population' in group['description'].lower():
        print(f"{group['name']}: {group['description']}")

# Get detailed variables for a specific table
b01003_vars = api.fetch_group_variables("acs/acs5", 2023, "B01003")
print(f"\nVariables in B01003:")
for var_code, var_info in b01003_vars['variables'].items():
    if var_code.endswith('E'):  # Estimates only
        print(f"  {var_code}: {var_info.get('label', 'N/A')}")
```

### Example 2: Building Table-Level Index

```bash
# Run the new table-level index builder
python index/build_index_tables.py

# Expected output:
# INFO - Initializing table collection: census_tables
# INFO - Processing dataset: acs/acs5
# INFO - Aggregated 450 unique tables
# INFO - Upserting 450 tables to ChromaDB...
# INFO - Index build complete! Total tables indexed: 450
# INFO - Test query 'total population' results:
#   - B01003: Total Population
#   - B01001: Sex by Age
#   - ...
```

### Example 3: Testing Category Selection

```python
# Test the category selector

from src.utils.category_selector import CategorySelector

selector = CategorySelector()

# Test different query types
queries = [
    {"original_text": "population of NYC", "measures": ["population"]},
    {"original_text": "give me an overview", "measures": ["demographics"]},
    {"original_text": "Hispanic population in Texas", "measures": ["hispanic"]},
]

for query in queries:
    category, confidence = selector.select_category(query)
    print(f"Query: {query['original_text']}")
    print(f"  Category: {category} (confidence: {confidence:.2f})\n")
```

---

## Checklist for Implementation

### Phase 8 Checklist
- [ ] Create `src/utils/census_groups_api.py`
- [ ] Create `index/build_index_tables.py`
- [ ] Update `config.py` with table-level settings
- [ ] Update `src/nodes/retrieve.py` with table retrieval
- [ ] Update `src/state/types.py` with table_code field
- [ ] Run new index builder: `python index/build_index_tables.py`
- [ ] Test table retrieval with sample queries
- [ ] Verify accuracy improvements

### Phase 9 Checklist
- [ ] Update `config.py` with CENSUS_CATEGORIES
- [ ] Create `src/utils/category_selector.py`
- [ ] Update `src/utils/census_api_utils.py` with dynamic URL building
- [ ] Update `src/state/types.py` with category field
- [ ] Update `src/nodes/data.py` to use category-aware fetching
- [ ] Create `test_category_selection.py`
- [ ] Test all 5 categories with sample queries
- [ ] Verify category selection accuracy

---

**Document Version**: 1.0  
**Created**: October 9, 2025  
**Purpose**: Practical code templates for Phase 8 & 9 implementation  
**Status**: Ready for use


