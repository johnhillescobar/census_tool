"""
Text parsing utility functions for the Census app
"""

import re
from typing import Dict, Any, List


# Census-related keywords
CENSUS_KEYWORDS = {
    "census",
    "population",
    "population of",
    "income",
    "median income",
    "ACS",
    "tract",
    "county",
    "place",
    "decennial",
    "demographics",
    "household",
    "family",
    "age",
    "race",
    "ethnicity",
    "education",
    "employment",
    "housing",
    "rent",
    "mortgage",
    "poverty",
}

# Answer type indicators
SINGLE_INDICATORS = {
    "what is",
    "how many",
    "what's the",
    "total",
    "number of",
    "count of",
    "in 20",
    "for 20",  # Year-specific
}

SERIES_INDICATORS = {
    "from",
    "to",
    "trend",
    "over time",
    "yearly",
    "years",
    "between",
    "through",
    "across",
    "change",
}

TABLE_INDICATORS = {
    "breakdown",
    "by county",
    "by tract",
    "by state",
    "across",
    "compare",
    "comparison",
    "versus",
    "vs",
    "by",
    "each",
}

# Measure keywords and their normalized forms
MEASURE_MAPPINGS = {
    "population": ["population", "people", "residents", "inhabitants"],
    "median_income": ["median income", "income", "household income", "family income"],
    "unemployment": ["unemployment", "unemployed", "jobless"],
    "education": ["education", "degree", "college", "high school", "graduate"],
    "hispanic": ["hispanic", "latino", "latina", "hispanic or latino"],
    "race": ["race", "racial", "white", "black", "asian", "native"],
}

# Geography hints
GEO_HINTS = {
    "nyc": [
        "nyc",
        "new york city",
        "manhattan",
        "brooklyn",
        "queens",
        "bronx",
        "staten island",
    ],
    "california": [
        "california",
        "ca",
        "cal",
        "los angeles",
        "san francisco",
        "santa clara",
    ],
    "texas": ["texas", "tx", "houston", "dallas", "austin", "san antonio", "plano"],
    "florida": ["florida", "fl", "miami", "orlando", "tampa", "st petersburg"],
    "nation": ["nation", "national", "usa", "united states", "country", "america"],
}

# Time patterns
YEAR_PATTERN = r"\b(19|20)\d{2}\b"
YEAR_RANGE_PATTERN = r"\b(19|20)\d{2}\s*(?:to|-|through)\s*(19|20)\d{2}\b"


def extract_years(text: str) -> Dict[str, Any]:
    """Extract year information from text"""
    text_lower = text.lower()

    # Check for year ranges (e.g., "2012 to 2023", "2012-2023", "2012 through 2023")
    range_patterns = [
        r"\b(19|20\d{2})\s*(?:to|-|through)\s*(19|20\d{2})\b",
        r"\b(19\d{2}|20\d{2})\s*(?:to|-|through)\s*(19\d{2}|20\d{2})\b",
    ]

    for pattern in range_patterns:
        range_match = re.search(pattern, text_lower)
        if range_match:
            start_year = int(range_match.group(1))
            end_year = int(range_match.group(2))
            return {
                "start_year": min(start_year, end_year),
                "end_year": max(start_year, end_year),
            }

    # Check for single years
    years = re.findall(YEAR_PATTERN, text_lower)
    if years:
        year = int(years[0])
        return {"year": year}

    return {}


def extract_measures(text: str) -> List[str]:
    """Extract measure keywords from text"""
    text_lower = text.lower()
    measures = []

    for measure, keywords in MEASURE_MAPPINGS.items():
        if any(keyword in text_lower for keyword in keywords):
            measures.append(measure)

    return measures


def extract_geo_hint(text: str) -> str:
    """Extract geo hint from text"""
    text_lower = text.lower()

    for geo, hints in GEO_HINTS.items():
        if any(hint in text_lower for hint in hints):
            return geo

    return text


def determine_answer_type(text: str) -> str:
    """Determine if answer should be single value, series, or table"""
    text_lower = text.lower()

    # Check for table indicators first (most specific)
    if any(indicator in text_lower for indicator in TABLE_INDICATORS):
        return "table"

    # Check for series indicators
    if any(indicator in text_lower for indicator in SERIES_INDICATORS):
        return "series"

    # Check for single indicators
    if any(indicator in text_lower for indicator in SINGLE_INDICATORS):
        return "single"

    # Default to single value
    return "single"


def is_census_question(text: str) -> bool:
    """Determine if question is about census"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CENSUS_KEYWORDS)


def build_retrieval_query(intent: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """Build Chroma query string from intent and profile"""
    query_parts = []

    # Extract intent components
    measures = intent.get("measures", [])
    answer_type = intent.get("answer_type", "single")
    time_info = intent.get("time", {})

    # 1. Add measures with synonyms (agnostic approach)
    if measures:
        expanded_measures = add_measure_synonyms(measures)
        measures_text = " ".join(expanded_measures)
        query_parts.append(measures_text)

    # 2. Add answer_type hints (generic patterns)
    if answer_type == "series":
        query_parts.extend(["over time", "yearly", "trend", "temporal"])
    elif answer_type == "table":
        query_parts.extend(
            ["breakdown", "by geography", "comparison", "cross-tabulation"]
        )

    # 3. Add time hints
    if "year" in time_info:
        query_parts.append(f"year {time_info['year']}")
    elif "start_year" in time_info and "end_year" in time_info:
        query_parts.append(
            f"years {time_info['start_year']} to {time_info['end_year']}"
        )

    # 4. Add dataset hint
    preferred_dataset = profile.get("preferred_dataset", "acs/acs5")
    query_parts.append(f"dataset:{preferred_dataset}")

    # 5. Check for var_aliases in profile (boost relevance)
    var_aliases = profile.get("var_aliases", {})
    measures_phrase = " ".join(measures).lower()
    if measures_phrase in var_aliases:
        # Prepend var code to boost relevance
        var_code = var_aliases[measures_phrase]
        query_parts.insert(0, var_code)

    # Build final query
    query_string = " ".join(filter(None, query_parts))

    return query_string


def add_measure_synonyms(measures: List[str]) -> List[str]:
    """Add synonyms to measures (e.g., latino for hispanic)"""
    expanded_measures = measures.copy()

    # Create a mapping of common synonyms (case-insensitive)
    synonym_mappings = {
        "hispanic": ["latino", "latina"],
        "latino": ["hispanic"],
        "latina": ["hispanic"],
        "income": ["earnings", "wage", "salary"],
        "population": ["people", "residents", "inhabitants"],
        "unemployment": ["jobless", "unemployed"],
        "education": ["schooling", "academic"],
        "age": ["years old", "aged"],
        "household": ["family", "home"],
    }

    # Add synonyms for each measure
    for measure in measures:
        measure_lower = measure.lower()
        if measure_lower in synonym_mappings:
            synonyms = synonym_mappings[measure_lower]
            for synonym in synonyms:
                if synonym not in [m.lower() for m in expanded_measures]:
                    expanded_measures.append(synonym)

    return expanded_measures
