"""Phase 5 metadata inference for census_tables Chroma documents.

Minimal contract (index-only; consumed by TableSearchTool / future agent filters):

Existing Chroma fields (unchanged):
  candidate_id, table_code, table_name, description, dataset, category,
  year, years_available, data_types, uses_groups, provenance, source_url,
  schema_version, index_version

Phase 5 additions on each table document:
  primary_topic  — canonical domain tag for filtering defaults
                   (population | housing | income | employment | education |
                    race_ethnicity | general)
  breadth        — broad headline table vs detailed breakdown (broad | detailed)
  universe       — short phrase for who/what is counted (table-level proxy)

Goal: agent can prefer broad population tables (e.g. B01003) over housing
tables when the user asks an underspecified population question.
"""

from __future__ import annotations

import re
from typing import Literal

PrimaryTopic = Literal[
    "population",
    "housing",
    "income",
    "employment",
    "education",
    "race_ethnicity",
    "general",
]
Breadth = Literal["broad", "detailed"]

_DETAIL_TABLE_CODE_PREFIXES: tuple[tuple[str, PrimaryTopic], ...] = (
    ("B01", "population"),
    ("C01", "population"),
    ("B05", "race_ethnicity"),
    ("C05", "race_ethnicity"),
    ("B19", "income"),
    ("C19", "income"),
    ("B23", "employment"),
    ("C23", "employment"),
    ("B25", "housing"),
    ("C25", "housing"),
    ("B26", "housing"),
    ("C26", "housing"),
)

_NAME_TOPIC_KEYWORDS: tuple[tuple[tuple[str, ...], PrimaryTopic], ...] = (
    (("population", "people", "residents", "inhabitants"), "population"),
    (("housing", "tenure", "occupancy", "housing unit", "housing units"), "housing"),
    (("income", "earnings", "poverty", "economic"), "income"),
    (("employment", "unemployment", "labor force", "working"), "employment"),
    (("education", "schooling", "college", "degree", "academic"), "education"),
    (("race", "ethnicity", "hispanic", "latino"), "race_ethnicity"),
)

_BROAD_NAME_MARKERS = (
    "total population",
    "median household income",
    "median age",
    "total housing units",
    "occupied housing units",
    "selected economic characteristics",
    "selected social characteristics",
    "selected housing characteristics",
    "demographic and housing",
    "demographic profile",
)

_DETAILED_NAME_MARKERS = (
    " by ",
    "sex by",
    "age by",
    "race by",
    "hispanic or latino",
    "selected characteristics",
    "detailed",
    "subgroup",
)


def _normalized_table_code(table_code: str) -> str:
    return table_code.strip().upper()


def infer_primary_topic(table_code: str, table_name: str) -> PrimaryTopic:
    """Return a single canonical topic for agent filtering and defaults."""
    code = _normalized_table_code(table_code)
    for prefix, topic in _DETAIL_TABLE_CODE_PREFIXES:
        if code.startswith(prefix):
            return topic

    name = table_name.lower()
    matched: list[PrimaryTopic] = []
    for keywords, topic in _NAME_TOPIC_KEYWORDS:
        if any(keyword in name for keyword in keywords):
            matched.append(topic)

    if not matched:
        return "general"
    if "housing" in matched and "population" in matched:
        housing_terms = ("housing", "tenure", "occupancy", "unit")
        if any(term in name for term in housing_terms):
            return "housing"
        return "population"
    return matched[0]


def infer_breadth(table_code: str, table_name: str, category: str) -> Breadth:
    """Classify headline vs breakdown tables for breadth-first agent defaults."""
    name = table_name.lower()
    code = _normalized_table_code(table_code)

    if category in {"profile", "cprofile"}:
        return "broad"
    if category == "subject" and not any(marker in name for marker in _DETAILED_NAME_MARKERS):
        return "broad"

    if any(marker in name for marker in _BROAD_NAME_MARKERS):
        return "broad"
    if any(marker in name for marker in _DETAILED_NAME_MARKERS):
        return "detailed"

    # Detail demographic headline totals (e.g. B01003 Total Population).
    if code.startswith(("B01", "C01")) and re.fullmatch(r"[BC]\d{5}", code) and code.endswith("003"):
        return "broad"

    return "detailed"


def infer_universe(table_code: str, table_name: str, primary_topic: PrimaryTopic) -> str:
    """Table-level universe proxy until group-variable fetch is indexed."""
    name = table_name.strip()
    if name:
        return name

    fallback = {
        "population": "Total population",
        "housing": "Housing units",
        "income": "Households",
        "employment": "Population 16 years and over",
        "education": "Population 25 years and over",
        "race_ethnicity": "Total population",
        "general": "",
    }
    return fallback.get(primary_topic, "")


def enrich_table_info(table_info: dict) -> dict[str, str]:
    """Return Phase 5 metadata fields for a table_info aggregate dict."""
    table_code = str(table_info.get("table_code", ""))
    table_name = str(table_info.get("table_name", ""))
    category = str(table_info.get("category", "detail"))
    primary_topic = infer_primary_topic(table_code, table_name)
    return {
        "primary_topic": primary_topic,
        "breadth": infer_breadth(table_code, table_name, category),
        "universe": infer_universe(table_code, table_name, primary_topic),
    }
