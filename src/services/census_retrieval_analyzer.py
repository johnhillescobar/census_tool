"""Search-language analysis boundary for grounded Census catalog retrieval."""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

_SPACE = re.compile(r"\s+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_LEADING_REQUEST = re.compile(
    r"^(?:please\s+)?(?:show|give|tell|find|get|compare|what(?:'s| is| are)?|how many|how much)\s+",
    re.IGNORECASE,
)
_GEO_LEVEL = re.compile(
    r"\b(block groups?|tracts?|county subdivisions?|count(?:y|ies)|places?|cities|states?|"
    r"zip code tabulation areas?|zctas?|metros?|metropolitan areas?|nation(?:al)?)\b",
    re.IGNORECASE,
)
_AREA_TAIL = re.compile(r"\b(?:in|within|across|for|of)\s+(.+)$", re.IGNORECASE)
_AREA_SPLIT = re.compile(r"\s*(?:,|;|\band\b|\bversus\b|\bvs\.?)\s*", re.IGNORECASE)
# Bare population intent only — do not expand "population by sex", median income, etc.
_BARE_POPULATION_INTENT = re.compile(r"^(?:total\s+)?population$", re.IGNORECASE)
_POPULATION_TABLE_SEARCH_HINT = "sex by age B01001 total population"


class CensusRetrievalAnalysis(BaseModel):
    """Only natural-language search phrases cross the analyzer boundary."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    table_search_text: str = Field(min_length=1)
    geography_search_text: str = Field(min_length=1)
    area_search_texts: list[str] = Field(default_factory=list)
    geography_explicit: bool = False


class CensusRetrievalAnalyzer(Protocol):
    """Interface for a later prompt-backed analyzer."""

    def analyze(self, question: str) -> CensusRetrievalAnalysis: ...


def _clean(text: str) -> str:
    return _SPACE.sub(" ", text).strip(" \t\n,;?.")


def _expand_table_search_text(table_text: str) -> str:
    """Bias bare population queries toward canonical ACS sex-by-age / total-population tables."""
    cleaned = _clean(table_text)
    if _BARE_POPULATION_INTENT.fullmatch(cleaned):
        return _POPULATION_TABLE_SEARCH_HINT
    return cleaned


class DeterministicCensusRetrievalAnalyzer:
    """Conservative offline baseline; it never emits FIPS or geo_for/geo_in tokens."""

    def analyze(self, question: str) -> CensusRetrievalAnalysis:
        normalized = _clean(question)
        if not normalized:
            raise ValueError("question is required")

        level_matches = [match.group(0) for match in _GEO_LEVEL.finditer(normalized)]
        geography_search = _clean(" ".join(level_matches)) if level_matches else "United States national geography"

        area_searches: list[str] = []
        area_match = _AREA_TAIL.search(normalized)
        if area_match:
            tail = _YEAR.sub("", area_match.group(1))
            tail = re.sub(r"\bfor\s*$", "", tail, flags=re.IGNORECASE)
            if not _clean(tail):
                area_match = None
        if area_match:
            for phrase in _AREA_SPLIT.split(tail):
                cleaned = _clean(phrase)
                if cleaned and not _GEO_LEVEL.fullmatch(cleaned):
                    area_searches.append(cleaned)
        area_searches = list(dict.fromkeys(area_searches))

        table_text = normalized[: area_match.start()] if area_match else normalized
        table_text = _LEADING_REQUEST.sub("", table_text)
        table_text = _YEAR.sub("", table_text)
        table_text = _GEO_LEVEL.sub("", table_text)
        table_text = re.sub(r"\b(?:for|in|during)\s*$", "", table_text, flags=re.IGNORECASE)
        table_text = _expand_table_search_text(_clean(table_text) or normalized)

        return CensusRetrievalAnalysis(
            question=normalized,
            table_search_text=table_text,
            geography_search_text=geography_search,
            area_search_texts=area_searches,
            geography_explicit=bool(level_matches or area_match),
        )


_BASELINE_ANALYZER = DeterministicCensusRetrievalAnalyzer()


def analyze_retrieval_request(
    question: str,
    *,
    analyzer: CensusRetrievalAnalyzer | None = None,
) -> CensusRetrievalAnalysis:
    """Analyze a question through an injectable search-language-only interface."""
    return (analyzer or _BASELINE_ANALYZER).analyze(question)


__all__ = [
    "CensusRetrievalAnalysis",
    "CensusRetrievalAnalyzer",
    "DeterministicCensusRetrievalAnalyzer",
    "analyze_retrieval_request",
]
