"""
Configuration constants for Census Graph App
Centralized settings for retention, API limits, and dataset configurations
"""

# Retention Settings
RETENTION_DAYS = 90
CACHE_MAX_FILES = 2000  # Optional: maximum number of cached files
CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024  # Optional: 2 GB cache size limit

# Census API Settings
CENSUS_API_TIMEOUT = 30  # seconds
CENSUS_API_MAX_RETRIES = 6
CENSUS_API_BACKOFF_FACTOR = 0.5  # exponential backoff: 0.5s, 1s, 2s, 4s, 8s, 16s
CENSUS_API_VARIABLE_LIMIT = 48  # maximum variables per request

# Concurrency Settings
MAX_CONCURRENCY = 5  # maximum parallel requests

# Chroma Settings
CHROMA_PERSIST_DIRECTORY = "./chroma"
CHROMA_COLLECTION_NAME = "census_vars"
CHROMA_EMBEDDING_MODEL = "text-embedding-3-large"

# Census Datasets Configuration
DEFAULT_DATASETS = [
    ("acs/acs5", list(range(2012, 2024))),  # 2012-2023
]

# Optional datasets (commented out, ready to enable)
# OPTIONAL_DATASETS = [
#     ("acs/acs1", list(range(2012, 2024))),  # 2012-2023
#     ("dec/pl", [2020]),  # 2020
# ]

# Default Geography Settings
DEFAULT_GEO = {
    "level": "place",
    "filters": {"for": "place:51000", "in": "state:36"},  # NYC
}

# File Format Settings
DEFAULT_FILE_FORMAT = "csv"  # TODO: switch to parquet later for speed
PREVIEW_ROWS = 5  # number of rows to keep in memory preview

# Message Management
MESSAGE_THRESHOLD = 20  # trigger summarization when messages exceed this
MESSAGE_TRIM_COUNT = 8  # keep last N messages after summarization

# Retrieval Settings
RETRIEVAL_TOP_K = 12  # number of candidates to retrieve from Chroma
CONFIDENCE_THRESHOLD = 0.7  # minimum confidence for automatic selection

# Geography Code Mappings
GEOGRAPHY_MAPPINGS = {
    "nyc": {"level": "place", "filters": {"for": "place:51000", "in": "state:36"}},
    "new_york_city": {
        "level": "place",
        "filters": {"for": "place:51000", "in": "state:36"},
    },
    "nation": {"level": "nation", "filters": {"for": "us:1"}},
}

# Supported Geography Levels
SUPPORTED_GEO_LEVELS = {
    "place": "for=place:PLACE&in=state:STATE",
    "state": "for=state:STATE",
    "county": "for=county:COUNTY&in=state:STATE",
    "nation": "for=us:1",
    # TODO: Add support for tracts and block groups
    # "tract": "for=tract:&in=state:SS&in=county:CCC",
    # "block_group": "for=block group:&in=state:SS&in=county:CCC&in=tract:TTTTTT",
}

# Variable Fallbacks (when retrieval fails)
VARIABLE_FALLBACKS = {
    "population": "B01003_001E",
    "hispanic_median_income": "B19013I_001E",
    "median_income": "B19013_001E",
}

PREVIEW_ROWS = 5
