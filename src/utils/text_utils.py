"""
Text parsing utility functions for the Census app
"""

import re
from typing import Dict, Any, List
import pandas as pd
import logging
from pathlib import Path


from src.state.types import CensusState
from config import PREVIEW_ROWS

logger = logging.getLogger(__name__)


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
    "illinois": ["illinois", "il", "chicago"],
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
        print("geo:", geo)
        print("hints:", hints)
        if any(
            hint in text_lower
            or text_lower.startswith(f"{hint}")
            or text_lower.endswith(f"{hint}")
            or text_lower == hint
            for hint in hints
        ):
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


def format_number_with_commas(number: float) -> str:
    """Format a number with commas"""
    try:
        if isinstance(number, (int, float)):
            return f"{number:,.0f}"
        else:
            return str(number)

    except Exception as e:
        logger.error(f"Error formatting number with commas: {str(e)}")
        return str(number)


# DELETE THIS ONE LATER. USE extract_year_from_dataset instead
def extract_year_from_key(key: str) -> str:
    """Extract year from dataset key"""
    year_match = re.search(r"(\d{4})", key)
    return year_match.group(1) if year_match else "Unknown"


def extract_year_from_dataset(dataset_key: str) -> str:
    """Extract year from dataset key (e.g., 'B01003_001E_place_2023' -> '2023')"""

    year_match = re.search(r"(\d{4})$", dataset_key)
    return year_match.group(1) if year_match else "Unknown"


def extract_dataset_from_key(key: str) -> str:
    """Extract dataset name from dataset key"""
    if "acs" in key.lower():
        return "ACS 5-Year Estimates"
    elif "dec" in key.lower():
        return "Decennial Census"
    else:
        return "Census Dataset"


def save_consolidated_table(
    data, table_type: str, geo: Dict[str, Any], intent: Dict[str, Any]
) -> str:
    """Save a consolidated table to data directory"""

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Generate filename
    geo_name = geo.get("display_name", "Unknown").replace(" ", "_").lower()
    measures = "-".join(intent.get("measures", ["data"]))
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{measures}_{geo_name}_{table_type}_{timestamp}.csv"
    file_path = data_dir / filename

    try:
        if isinstance(data, list):
            # Convert to a list of dicts to DataFrame
            df = pd.DataFrame(data)
        else:
            df = data

        df.to_csv(file_path, index=False)
        return str(file_path)

    except Exception as e:
        logger.error(f"Error saving consolidated table: {str(e)}")
        return ""


def extract_variable_from_key(key: str) -> str:
    """Extract variable code from dataset key (e.g., 'B01003_001E_place_2023' -> 'B01003_001E')"""

    var_match = re.search(r"([A-Z]\d+[A-Z]?_\d+[A-Z]?)", key)
    return var_match.group(1) if var_match else "Unknown"


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


def format_single_value_answer(
    datasets: Dict[str, str],
    previews: Dict[str, Any],
    geo: Dict[str, Any],
    intent: Dict[str, Any],
) -> Dict[str, Any]:
    """Format a single value answer"""

    # Get the first dataset (should be only one for single value)
    dataset_key = list(datasets.keys())[0]
    file_path = datasets[dataset_key]
    preview = previews.get(dataset_key, [])

    if not preview or len(preview) < 2:
        return {
            "type": "single",
            "value": "Data not available",
            "geo": geo.get("display_name", "Unknown location"),
            "year": "Unknown",
            "dataset": "Unknown",
        }

    # Extract value from preview (first row, second column typically)
    try:
        value = preview[1][1] if len(preview) > 1 and len(preview[1]) > 1 else "N/A"
        geo_name = (
            preview[1][0]
            if len(preview) > 1 and len(preview[0]) > 0
            else geo.get("display_name", "Unknown")
        )

        # Format the value
        if isinstance(value, (int, float)) and value != "N/A":
            formatted_value = format_number_with_commas(value)
        else:
            formatted_value = str(value)

        # Extract year from dataset key or file path
        year = extract_year_from_dataset(dataset_key)

        return {
            "type": "single",
            "value": formatted_value,
            "geo": geo_name,
            "year": year,
            "dataset": extract_dataset_from_key(dataset_key),
            "variable": extract_variable_from_key(dataset_key),
        }

    except Exception as e:
        logger.error(f"Error formatting single value: {str(e)}")
        return {
            "type": "single",
            "value": "Error formatting data",
            "geo": geo.get("display_name", "Unknown location"),
            "year": "Unknown",
            "dataset": "Unknown",
        }


def format_series_answer(
    datasets: Dict[str, Any],
    previews: Dict[str, Any],
    geo: Dict[str, Any],
    intent: Dict[str, Any],
) -> Dict[str, Any]:
    """Format a series answer"""

    consolidated_data = []
    years = []

    for dataset_key, file_path in datasets.items():
        try:
            df = pd.read_csv(file_path)
            year = int(extract_year_from_dataset(dataset_key))
            years.append(year)

            # Get the value column (typically the last column)
            if len(df.columns) > 1:
                value_column = df.columns[1]
                value = df[value_column].iloc[0] if len(df) > 0 else None
                if value is not None and hasattr(value, "item"):  # numpy scalar
                    value = value.item()
                geo_value = (
                    df.iloc[0][0] if len(df) > 0 else geo.get("display_name", "Unknown")
                )
                if hasattr(geo_value, "item"):  # numpy scalar
                    geo_value = geo_value.item()
                consolidated_data.append(
                    {
                        "year": year,
                        "value": value,
                        "geo": str(geo_value),
                    }
                )

        except Exception as e:
            logger.error(f"Error consolidating series data: {str(e)}")
            continue

    if not consolidated_data:
        return {
            "type": "series",
            "data": [],
            "geo": geo.get("display_name", "Unknown"),
            "variable": "Unknown",
            "message": "No data available",
        }

    # Sort by year
    consolidated_data.sort(key=lambda x: x["year"])

    # Format values
    for item in consolidated_data:
        if isinstance(item["value"], (int, float)) and item["value"] is not None:
            item["formatted_value"] = format_number_with_commas(item["value"])
        else:
            item["formatted_value"] = (
                str(item["value"]) if item["value"] is not None else "N/A"
            )

    # Save consolidated table
    consolidated_file = save_consolidated_table(
        consolidated_data, "series", geo, intent
    )

    return {
        "type": "series",
        "data": consolidated_data,
        "geo": consolidated_data[0]["geo"]
        if consolidated_data
        else geo.get("display_name", "Unknown"),
        "variable": extract_variable_from_key(list(datasets.keys())[0]),
        "file_path": consolidated_file,
        "preview": consolidated_data[:PREVIEW_ROWS],
    }


def format_table_answer(
    datasets: Dict[str, str],
    previews: Dict[str, Any],
    geo: Dict[str, Any],
    intent: Dict[str, Any],
) -> Dict[str, Any]:
    """Format a table/breakdown answer"""

    # For table answers, we might have multiple variables or geographies
    # Load all datasets and create a consolidated table
    all_data = []

    for dataset_key, file_path in datasets.items():
        try:
            df = pd.read_csv(file_path)
            year = extract_year_from_dataset(dataset_key)
            variable = extract_variable_from_key(dataset_key)

            # Add year and variable to each row
            df_copy = df.copy()
            df_copy["year"] = year
            df_copy["variable"] = variable
            all_data.append(df_copy)

        except Exception as e:
            logger.error(f"Error loading table data: {str(e)}")
            continue

    if not all_data:
        return {
            "type": "table",
            "data": [],
            "message": "No data available",
        }

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)

    # Save consolidated table
    consolidated_file = save_consolidated_table(combined_df, "table", geo, intent)

    # Create preview
    preview_data = combined_df.head(PREVIEW_ROWS).to_dict("records")

    return {
        "type": "table",
        "data": preview_data,
        "total_rows": len(combined_df),
        "file_path": consolidated_file,
        "columns": list(combined_df.columns),
    }


def generate_footnotes(
    datasets: Dict[str, Any],
    geo: Dict[str, Any],
    intent: Dict[str, Any],
) -> List[str]:
    """Generate footnotes for a table answer"""

    footnotes = []

    # Add dataset info
    for dataset_key, file_path in datasets.items():
        year = extract_year_from_dataset(dataset_key)
        dataset = extract_dataset_from_key(dataset_key)
        variable = extract_variable_from_key(dataset_key)

        footnotes.append(f"Data from {dataset}, {year}, variable: {variable}")

    # Add geography information
    geo_name = geo.get("display_name", "Unknown")
    geo_level = geo.get("level", "Unknown")
    footnotes.append(f"Geography: {geo_name} at {geo_level} level")

    # Add data source
    footnotes.append("Source: U.S. Census Bureau")

    return footnotes


if __name__ == "__main__":
    text = "What's the population of Chicago?"
    print("extract_years(text):", extract_years(text))
    print("extract_measures(text):", extract_measures(text))
    print("extract_geo_hint(text):", extract_geo_hint(text))
    print("determine_answer_type(text):", determine_answer_type(text))
    print("is_census_question(text):", is_census_question(text))
    # print(format_number_with_commas(1000000))
    # print(extract_year_from_key("B01003_001E_place_2023"))
    # print(extract_year_from_dataset("B01003_001E_place_2023"))
    # print(extract_dataset_from_key("B01003_001E_place_2023"))
    # print(extract_variable_from_key("B01003_001E_place_2023"))
