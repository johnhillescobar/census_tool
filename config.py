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
CHROMA_TABLE_COLLECTION_NAME = "census_tables"
CHROMA_EMBEDDING_MODEL = "text-embedding-3-large"

# Census Datasets Configuration
DEFAULT_DATASETS = [
    # Detail Tables (B/C codes)
    ("acs/acs5", list(range(2012, 2024))),
    
    # Subject Tables (S codes) 
    ("acs/acs5/subject", list(range(2012, 2024))),
    
    # Profile Tables (DP codes)
    ("acs/acs1/profile", list(range(2012, 2024))),
    
    # Comparison Tables (CP codes)
    ("acs/acs5/cprofile", list(range(2014, 2024))),
    
    # Selected Population Profiles
    ("acs/acs1/spp", list(range(2014, 2024))),
]


# Census Category Metadata (for Phase 9)
CENSUS_CATEGORIES = {
    "detail": {
        "name": "Detail Tables",
        "path": "acs/acs5",
        "prefix": ["B", "C"],
        "description": "Detailed demographic tables with high granularity",
        "use_cases": ["specific breakdowns", "detailed demographics", "granular data"],
        "uses_groups": False,  # Individual variables
        "years": list(range(2012, 2024)),
        "groups_endpoint": "https://api.census.gov/data/{year}/acs/acs5/groups.json"
    },
    "subject": {
        "name": "Subject Tables",
        "path": "acs/acs5/subject",
        "prefix": ["S"],
        "description": "Topic-specific summary tables",
        "use_cases": ["overview", "summary", "topic overview", "demographic overview"],
        "uses_groups": True,  # Use group() function
        "years": list(range(2012, 2024)),
        "groups_endpoint": "https://api.census.gov/data/{year}/acs/acs5/subject/groups.json"
    },
    "profile": {
        "name": "Profile Tables",
        "path": "acs/acs1/profile",
        "prefix": ["DP"],
        "description": "Comprehensive demographic profiles",
        "use_cases": ["profile", "comprehensive", "full demographics"],
        "uses_groups": True,
        "years": list(range(2012, 2024)),
        "groups_endpoint": "https://api.census.gov/data/{year}/acs/acs1/profile/groups.json"
    },
    "cprofile": {
        "name": "Comparison Tables",
        "path": "acs/acs5/cprofile",
        "prefix": ["CP"],
        "description": "Multi-year comparison tables",
        "use_cases": ["compare", "comparison", "change over time", "trends"],
        "uses_groups": True,
        "years": list(range(2014, 2024)),  # Note: starts 2014
        "groups_endpoint": "https://api.census.gov/data/{year}/acs/acs5/cprofile/groups.json"
    },
    "spp": {
        "name": "Selected Population Profiles",
        "path": "acs/acs1/spp",
        "prefix": ["S0201"],
        "description": "Race and ethnicity-specific profiles",
        "use_cases": ["hispanic", "latino", "asian", "race", "ethnicity specific"],
        "uses_groups": True,
        "years": list(range(2014, 2024)),  # Note: starts 2014
        "groups_endpoint": "https://api.census.gov/data/{year}/acs/acs1/spp/groups.json"
    }
}

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
CONFIDENCE_THRESHOLD = 0.4  # minimum confidence for automatic selection

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
    "tract": "for=tract:&in=state:SS&in=county:CCC",
    "block_group": "for=block group:&in=state:SS&in=county:CCC&in=tract:TTTTTT",
    "congressional_district": "for=congressional district:CD&in=state:STATE",
    "zcta": "for=zip code tabulation area:ZCTA5",
}

SUPPORTED_GEOGRAPHY_LEVELS = {
    # Fully supported levels (your current implementation)
    "nation": {
        "supported": True,
        "requires_context": False,
        "description": "United States nationwide data",
    },
    "state": {
        "supported": True,
        "requires_context": False,
        "description": "State-level data",
    },
    "place": {
        "supported": True,
        "requires_context": True,  # Needs state context for accuracy
        "description": "City/town-level data",
    },
    "county": {
        "supported": True,
        "requires_context": True,  # Needs state context
        "description": "County-level data",
    },
    # Advanced levels (need special handling)
    "tract": {
        "supported": False,  # Not yet implemented
        "requires_context": True,
        "requires_county": True,  # Tracts need county context
        "description": "Census tract data (requires county specification)",
        "suggestion": "Try county-level data instead",
    },
    "block_group": {
        "supported": False,
        "requires_context": True,
        "requires_tract": True,
        "description": "Block group data (requires tract specification)",
        "suggestion": "Try county or tract-level data instead",
    },
    "congressional_district": {
        "supported": False,
        "requires_context": True,
        "description": "Congressional district data",
        "suggestion": "Try state-level data instead",
    },
    "zcta": {
        "supported": False,
        "requires_context": False,
        "description": "ZIP Code Tabulation Area data",
        "suggestion": "Try place or county-level data instead",
    },
}

# Variable Fallbacks (when retrieval fails)
VARIABLE_FALLBACKS = {
    "population": "B01003_001E",
    "hispanic_median_income": "B19013I_001E",
    "median_income": "B19013_001E",
}

PREVIEW_ROWS = 5

# Census Geocoding API Settings
CENSUS_GEOCODING_BASE_URL = "https://geocoding.geo.census.gov/geocoder"
CENSUS_GEOCODING_GEOGRAPHY_URL = "https://geocoding.geo.census.gov/geocoder"
GEOCODING_CACHE_TTL = 86400  # 24 hours
MAX_GEOCODING_RETRIES = 3
GEOCODING_TIMEOUT = 30  # seconds
