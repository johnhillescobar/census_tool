"""
Census API Utils
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Iterable, Optional
import requests
import time
from urllib.parse import quote
from dotenv import load_dotenv
import logging

from config import (
    CENSUS_API_TIMEOUT,
    CENSUS_API_MAX_RETRIES,
    CENSUS_API_BACKOFF_FACTOR,
)
from src.utils.chroma_utils import validate_and_fix_geo_params

# Load environment variables
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

_GEO_SAFE_CHARS = ":/()*"


def _combine_geo_in(
    geo_in: Optional[Dict[str, str]],
    chained_in: Optional[Iterable[Dict[str, str]]],
) -> Dict[str, str]:
    combined: Dict[str, str] = {} if geo_in is None else dict(geo_in)
    if chained_in:
        for in_dict in chained_in:
            if isinstance(in_dict, dict):
                combined.update(in_dict)
    return combined


def build_geo_filters(
    dataset: str,
    year: int,
    geo_for: Dict[str, str],
    geo_in: Optional[Dict[str, str]] = None,
    geo_in_chained: Optional[Iterable[Dict[str, str]]] = None,
) -> Dict[str, str]:
    """
    Produce encoded `for` / `in` parameters using hierarchy ordering.
    """
    combined_in = _combine_geo_in(geo_in, geo_in_chained)
    for_token, for_value, ordered_in = validate_and_fix_geo_params(
        dataset=dataset,
        year=year,
        geo_for=geo_for,
        geo_in=combined_in,
    )

    for_clause = f"{for_token}:{for_value}"
    encoded_for = quote(for_clause, safe=_GEO_SAFE_CHARS)

    encoded_in = None
    if ordered_in:
        in_clause = " ".join(f"{token}:{value}" for token, value in ordered_in)
        encoded_in = quote(in_clause, safe=_GEO_SAFE_CHARS)

    filters: Dict[str, str] = {"for": encoded_for}
    if encoded_in:
        filters["in"] = encoded_in

    return filters


def fetch_census_data(
    dataset: str, year: int, variables: List[str], geo: Dict[str, Any]
) -> Dict[str, Any]:
    """Fetch Census data from the Census API"""
    url = build_census_url(dataset, year, variables, geo)

    for attempt in range(CENSUS_API_MAX_RETRIES):
        try:
            response = requests.get(url, timeout=CENSUS_API_TIMEOUT)

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "url": url,
                    "attempt": attempt + 1,
                }

            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = (
                    int(retry_after)
                    if retry_after
                    else CENSUS_API_BACKOFF_FACTOR * (2**attempt)
                )
                logger.info(
                    f"Rate limit exceeded. Waiting {wait_time} seconds before retry..."
                )
                time.sleep(wait_time)
                continue

            elif 500 <= response.status_code < 600:
                logger.error(f"Server error. Attempt {attempt + 1} failed.")
                retry_after = response.headers.get("Retry-After")
                wait_time = CENSUS_API_BACKOFF_FACTOR * attempt
                time.sleep(wait_time)
                continue

            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "url": url,
                    "attempt": attempt + 1,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {str(e)}")
            if attempt == CENSUS_API_MAX_RETRIES - 1:
                return {
                    "success": False,
                    "error": f"Requests failed after {CENSUS_API_MAX_RETRIES} attempts: {str(e)}",
                    "url": url,
                    "attempt": attempt + 1,
                }
            wait_time = CENSUS_API_BACKOFF_FACTOR * (2**attempt)
            time.sleep(wait_time)

    return {
        "success": False,
        "error": "Max retries exceeded",
        "url": url,
        "attempt": CENSUS_API_MAX_RETRIES,
    }


def build_census_url(
    dataset: str, year: int, variables: List[str], geo: Dict[str, Any]
) -> str:
    """Build the Census API URL with support for complex geography patterns"""
    base_url = "https://api.census.gov/data"

    # Construct the URL
    url = f"{base_url}/{year}/{dataset}"

    # Handle variables - can be list of variables or group syntax
    if (
        isinstance(variables, list)
        and len(variables) == 1
        and variables[0].startswith("group(")
    ):
        # Group syntax for subject tables
        variables_str = variables[0]
    else:
        # Regular variable list
        variables_str = ",".join(variables)

    # Add the geography filters - assume values already encoded by build_geo_filters
    geo_filters = []
    for key, value in geo.get("filters", {}).items():
        if value is None:
            continue
        if isinstance(value, str) and " " in value and "%" not in value:
            encoded = quote(value, safe=_GEO_SAFE_CHARS)
        else:
            encoded = value
        geo_filters.append(f"{key}={encoded}")

    # Add Census API key if available
    census_api_key = os.getenv("CENSUS_API_KEY")
    if census_api_key:
        geo_filters.append(f"key={census_api_key}")

    # Combine all parameters
    params = [f"get={variables_str}"] + geo_filters
    param_string = "&".join(params)

    return f"{url}?{param_string}"


def build_census_url_from_metadata(
    table_metadata: Dict, year: int, geo: Dict[str, Any], variables: List[str] = None
) -> str:
    """
    Build Census API URL from table metadata

    Args:
        table_metadata: Dict from ChromaDB with keys:
            - table_code: str (e.g., "S0101", "DP03", "B01003")
            - category: str (e.g., "subject", "profile", "detail")
            - dataset: str (e.g., "acs/acs5/subject")
            - uses_groups: bool (True/False)
        year: Census year (e.g., 2023)
        geo: Geography dict with 'filters' key
        variables: List of variable codes (only needed if uses_groups=False)

    Returns:
        Complete Census API URL string

    Examples:
        # Subject table
        metadata = {'table_code': 'S0101', 'uses_groups': True,
                    'dataset': 'acs/acs5/subject', 'category': 'subject'}
        url = build_census_url_from_metadata(metadata, 2023, {'filters': {'for': 'state:*'}})
        # → https://api.census.gov/data/2023/acs/acs5/subject?get=group(S0101)&for=state:*

        # Detail table
        metadata = {'table_code': 'B01003', 'uses_groups': False,
                    'dataset': 'acs/acs5', 'category': 'detail'}
        url = build_census_url_from_metadata(metadata, 2023,
                                             {'filters': {'for': 'state:*'}},
                                             variables=['B01003_001E'])
        # → https://api.census.gov/data/2023/acs/acs5?get=B01003_001E&for=state:*
    """

    # Extract what you need from table_metadata
    table_code = table_metadata["table_code"]
    category = table_metadata["category"]
    uses_groups = table_metadata["uses_groups"]

    # Bring basic URL
    base_url = "https://api.census.gov/data"

    # Determine the dataset path based on category
    if category == "detail":
        dataset_path = "acs/acs5"
    elif category == "profile":
        dataset_path = "acs/acs1/profile"
    elif category == "subject":
        dataset_path = "acs/acs5/subject"
    elif category == "cprofile":
        dataset_path = "acs/acs5/cprofile"
    elif category == "spp":
        dataset_path = "acs/acs1/spp"
    else:
        if not variables:
            raise ValueError("variables required when uses_groups=False")
        get_param = ",".join(variables)  # ← Use the parameter!

    # Build the get parameter
    if uses_groups:
        get_param = f"group({table_code})"
    else:
        get_param = ",".join(variables)

    # Build the geography filters
    filters = geo.get("filters", {})
    geo_filters = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, str) and " " in value and "%" not in value:
            encoded = quote(value, safe=_GEO_SAFE_CHARS)
        else:
            encoded = value
        geo_filters.append(f"{key}={encoded}")

    # Add Census API key if available
    census_api_key = os.getenv("CENSUS_API_KEY")
    if census_api_key:
        geo_filters.append(f"key={census_api_key}")

    # Combine parameters
    params = [f"get={get_param}"] + geo_filters
    param_string = "&".join(params)

    return f"{base_url}/{year}/{dataset_path}?{param_string}"


def parse_census_response(response: Dict) -> Dict:
    """Parse the Census API response"""
    pass


def handle_api_errors(response: Dict) -> Dict:
    """Handle Census API errors"""
    pass


def test_build_census_url_from_metadata():
    """Test URL building for all 5 categories"""

    # Test 1: Detail table (B01003)
    print("Test 1: Detail table")
    metadata_detail = {
        "table_code": "B01003",
        "category": "detail",
        "dataset": "acs/acs5",
        "uses_groups": False,
    }
    url = build_census_url_from_metadata(
        metadata_detail,
        year=2023,
        geo={"filters": {"for": "state:*"}},
        variables=["B01003_001E"],
    )
    expected = "https://api.census.gov/data/2023/acs/acs5?get=B01003_001E&for=state:*"
    print(f"  Generated: {url}")
    print(f"  Expected:  {expected}")
    print(f"  Match: {url == expected}\n")

    # Test 2: Subject table (S0101)
    print("Test 2: Subject table")
    metadata_subject = {
        "table_code": "S0101",
        "category": "subject",
        "dataset": "acs/acs5/subject",
        "uses_groups": True,
    }
    url = build_census_url_from_metadata(
        metadata_subject, year=2023, geo={"filters": {"for": "state:*"}}
    )
    expected = (
        "https://api.census.gov/data/2023/acs/acs5/subject?get=group(S0101)&for=state:*"
    )
    print(f"  Generated: {url}")
    print(f"  Expected:  {expected}")
    print(f"  Match: {url == expected}\n")

    # Test 3: Profile table (DP03)
    print("Test 3: Profile table")
    metadata_profile = {
        "table_code": "DP03",
        "category": "profile",
        "dataset": "acs/acs1/profile",
        "uses_groups": True,
    }
    url = build_census_url_from_metadata(
        metadata_profile, year=2023, geo={"filters": {"for": "state:06"}}
    )
    expected = (
        "https://api.census.gov/data/2023/acs/acs1/profile?get=group(DP03)&for=state:06"
    )
    print(f"  Generated: {url}")
    print(f"  Expected:  {expected}")
    print(f"  Match: {url == expected}\n")

    # Test 4: Comparison table (CP03)
    print("Test 4: Comparison table")
    metadata_cprofile = {
        "table_code": "CP03",
        "category": "cprofile",
        "dataset": "acs/acs5/cprofile",
        "uses_groups": True,
    }
    url = build_census_url_from_metadata(
        metadata_cprofile, year=2023, geo={"filters": {"for": "state:*"}}
    )
    expected = (
        "https://api.census.gov/data/2023/acs/acs5/cprofile?get=group(CP03)&for=state:*"
    )
    print(f"  Generated: {url}")
    print(f"  Expected:  {expected}")
    print(f"  Match: {url == expected}\n")


def test_real_census_api():
    """Test with actual Census API calls"""
    import requests

    # Test 1: Subject table S0101 for California
    print("Calling real Census API for S0101 (Age and Sex)...")
    metadata = {
        "table_code": "S0101",
        "category": "subject",
        "dataset": "acs/acs5/subject",
        "uses_groups": True,
    }
    url = build_census_url_from_metadata(
        metadata,
        year=2022,  # Use 2022 (2023 might not be available yet)
        geo={"filters": {"for": "state:06"}},  # California
    )

    print(f"URL: {url}")
    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        data = response.json()
        print(f" SUCCESS! Received {len(data)} rows")
        print(f"Columns: {data[0][:5]}...")  # First 5 columns
        print(f"First data row: {data[1][:5]}...")
    else:
        print(f" Error: {response.status_code}")
        print(f"Response: {response.text[:200]}")


if __name__ == "__main__":
    test_build_census_url_from_metadata()
    test_real_census_api()
