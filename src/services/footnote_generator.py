"""
Footnote generation utility for Census data queries.

Generates dynamic footnotes based on census data metadata, including:
- Data source citations
- Methodology notes
- Disclaimers
- Table codes used
"""

import re
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def extract_year_from_data(census_data: Dict) -> str:
    """Extract year from census data or URL"""
    try:
        # Try to get from URL
        url = census_data.get("url", "")
        if url:
            # Match patterns like /2023/ or /2015/
            year_match = re.search(r"/(\d{4})/", url)
            if year_match:
                return year_match.group(1)

        # Try to get from data headers
        data = census_data.get("data", [])
        if data and len(data) > 0:
            headers = data[0]
            if "YEAR" in headers or "Year" in headers:
                # Get from first data row
                if len(data) > 1:
                    year_idx = (
                        headers.index("YEAR")
                        if "YEAR" in headers
                        else headers.index("Year")
                    )
                    return str(data[1][year_idx])

        # Default to most recent common year
        return "2023"
    except Exception as e:
        logger.warning(f"Could not extract year from data: {e}")
        return "2023"


def extract_dataset_from_data(census_data: Dict) -> str:
    """Extract dataset type from census data URL"""
    try:
        url = census_data.get("url", "")
        if url:
            # Match ACS dataset patterns
            if "acs5" in url or "acs/acs5" in url:
                return "5-Year Estimates"
            elif "acs1" in url or "acs/acs1" in url:
                return "1-Year Estimates"
            elif "acs3" in url or "acs/acs3" in url:
                return "3-Year Estimates"

        # Default
        return "5-Year Estimates"
    except Exception as e:
        logger.warning(f"Could not extract dataset from data: {e}")
        return "5-Year Estimates"


def extract_table_codes_from_reasoning(reasoning_trace: str) -> List[str]:
    """Extract Census table codes from reasoning trace"""
    try:
        # Match patterns like B01003, S1903, DP05, etc.
        table_pattern = r"\b([BCSDP]{1,2}\d{5}[A-Z]?)\b"
        matches = re.findall(table_pattern, reasoning_trace, re.IGNORECASE)

        # Remove duplicates and return
        return list(set([m.upper() for m in matches]))
    except Exception as e:
        logger.warning(f"Could not extract table codes: {e}")
        return []


def generate_footnotes(
    census_data: Dict, data_summary: str, reasoning_trace: str
) -> List[str]:
    """
    Generate footnotes dynamically based on census data used.

    Args:
        census_data: Census API response data
        data_summary: Brief summary of the data
        reasoning_trace: Agent's reasoning steps

    Returns:
        List of footnote strings
    """
    footnotes = []

    try:
        # Extract metadata from census_data
        year = extract_year_from_data(census_data)
        dataset = extract_dataset_from_data(census_data)
        table_codes = extract_table_codes_from_reasoning(reasoning_trace)

        # Static footnote: Data source citation (always included)
        footnotes.append(
            f"Source: U.S. Census Bureau, {year} American Community Survey {dataset}."
        )

        # Static footnote: Statistical significance disclaimer
        footnotes.append(
            "Margins of error not shown. For statistical significance, refer to Census Bureau documentation."
        )

        # Dynamic footnote: Inflation adjustment for income data
        if (
            "inflation-adjusted" in data_summary.lower()
            or "income" in data_summary.lower()
            or "S1903" in reasoning_trace
        ):
            footnotes.append(
                f"Income values are adjusted for {year} inflation using the Consumer Price Index (CPI-U)."
            )

        # Dynamic footnote: Table codes used
        if table_codes:
            table_list = ", ".join(sorted(table_codes))
            footnotes.append(f"Census table(s) used: {table_list}.")

        # Static footnote: General disclaimer
        footnotes.append(
            "This tool is for informational purposes only. Verify critical data at census.gov."
        )

        logger.info(f"Generated {len(footnotes)} footnotes")
        return footnotes

    except Exception as e:
        logger.error(f"Error generating footnotes: {e}")
        # Return basic footnote on error
        return [
            "Source: U.S. Census Bureau, American Community Survey.",
            "This tool is for informational purposes only. Verify critical data at census.gov.",
        ]
