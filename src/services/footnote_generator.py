"""
Footnote generation utility for Census data queries.

Generates dynamic footnotes based on census data metadata, including:
- Data source citations
- Methodology notes
- Disclaimers
- Table codes used
"""

import re
from typing import List
import logging

from src.domain.census_tool_contract import StrictCensusApiResponse

logger = logging.getLogger(__name__)


def _year_from_strict(census_data: StrictCensusApiResponse) -> str:
    """Resolve survey year from typed API response when available."""
    if census_data.success and census_data.request is not None:
        return str(census_data.request.year)
    logger.debug("Footnote year fallback: no successful typed request on census_data")
    return "2023"


def _dataset_label_from_strict(census_data: StrictCensusApiResponse) -> str:
    """Human-readable ACS product label from typed request dataset."""
    if census_data.success and census_data.request is not None:
        raw = census_data.request.dataset
        s = raw.lower() if isinstance(raw, str) else str(raw).lower()
        if "acs5" in s or "acs/acs5" in s:
            return "5-Year Estimates"
        if "acs1" in s:
            return "1-Year Estimates"
        if "acs3" in s:
            return "3-Year Estimates"
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
    census_data: StrictCensusApiResponse,
    data_summary: str,
    reasoning_trace: str,
) -> List[str]:
    """
    Generate footnotes from typed Census response and agent text.

    Args:
        census_data: Validated API response (use no_strict_census_payload when absent).
        data_summary: Brief summary of the data
        reasoning_trace: Agent's reasoning steps

    Returns:
        List of footnote strings
    """
    footnotes = []

    try:
        year = _year_from_strict(census_data)
        dataset = _dataset_label_from_strict(census_data)
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
