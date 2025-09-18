from typing import Dict, List, Any
import requests
import time
from config import (
    CENSUS_API_TIMEOUT,
    CENSUS_API_MAX_RETRIES,
    CENSUS_API_BACKOFF_FACTOR,
)

import logging

logger = logging.getLogger(__name__)


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
    """Build the Census API URL"""
    base_url = "https://api.census.gov/data"

    # Construct the URL
    url = f"{base_url}/{year}/{dataset}"

    # Add variables paramater
    variables_str = ",".join(variables)

    # Add the geography filters
    geo_filters = []
    for key, value in geo.get("filters", {}).items():
        geo_filters.append(f"{key}={value}")

    # Combine all parameters
    params = [f"get={variables_str}"] + geo_filters
    param_string = "&".join(params)

    return f"{url}?{param_string}"


def parse_census_response(response: Dict) -> Dict:
    """Parse the Census API response"""
    pass


def handle_api_errors(response: Dict) -> Dict:
    """Handle Census API errors"""
    pass
