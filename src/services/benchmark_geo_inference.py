import re

import us

from src.domain.benchmark_contract import GeographyLevel
from src.domain.benchmark_geo_inference import DetectedGeoContext

NATIONAL_PATTERN = re.compile(r"\b(us|u\.s\.|united states|national)\b", re.IGNORECASE)
STATE_PATTERN = re.compile(r"\b(state|states|statewide)\b", re.IGNORECASE)
COUNTY_PATTERN = re.compile(r"\b(county|counties)\b", re.IGNORECASE)
PLACE_PATTERN = re.compile(r"\b(city|cities|place|places)\b", re.IGNORECASE)
CBSA_PATTERN = re.compile(r"\b(cbsa|metro|metropolitan)\b", re.IGNORECASE)

COMPARE_SPLIT_PATTERN = re.compile(r"\b(compare|vs|versus|against|and|,)\b", re.IGNORECASE)

NOISE_WORDS = frozenset(
    {
        "compare",
        "vs",
        "versus",
        "against",
        "and",
        "in",
        "for",
        "the",
        "a",
        "an",
        "of",
        "by",
        "from",
        "to",
        "with",
        "population",
        "people",
        "residents",
        "inhabitants",
        "median",
        "income",
        "household",
        "family",
        "unemployment",
        "unemployed",
        "jobless",
        "education",
        "degree",
        "college",
        "graduate",
        "hispanic",
        "latino",
        "latina",
        "race",
        "racial",
        "data",
        "trends",
        "trend",
        "show",
        "what",
        "is",
        "are",
        "me",
    }
)

YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Two-letter abbreviations that are common English words; lowercase matches are ignored.
AMBIGUOUS_STATE_ABBREVIATIONS = frozenset(
    {
        "al",
        "co",
        "de",
        "hi",
        "id",
        "in",
        "la",
        "ma",
        "md",
        "me",
        "mt",
        "nd",
        "ok",
        "or",
        "pa",
        "sd",
        "ut",
        "va",
        "wa",
    }
)


def _state_abbreviation_in_text(abbr: str, text: str) -> bool:
    """Match state abbreviations case-insensitively without English-word false positives."""
    if len(abbr) != 2:
        return False
    for match in re.finditer(rf"\b{re.escape(abbr)}\b", text, re.IGNORECASE):
        token = match.group(0)
        if token.islower() and token.lower() in AMBIGUOUS_STATE_ABBREVIATIONS:
            continue
        return True
    return False


GEO_SUFFIXES = (
    "county",
    "counties",
    "city",
    "cities",
    "place",
    "places",
    "town",
    "towns",
)


def extract_geo_candidates(text: str) -> list[str]:
    """Parse compare phrases into candidate place names."""
    if not text:
        return []

    segments = COMPARE_SPLIT_PATTERN.split(text)
    candidates: list[str] = []

    for segment in segments:
        cleaned = YEAR_PATTERN.sub("", segment)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        tokens = [token.strip() for token in cleaned.split() if token.strip()]
        if not tokens:
            continue

        phrase_tokens: list[str] = []
        for token in tokens:
            if token.lower() in NOISE_WORDS:
                if phrase_tokens:
                    candidates.append(" ".join(phrase_tokens))
                    phrase_tokens = []
                continue
            phrase_tokens.append(token)

        if phrase_tokens:
            candidates.append(" ".join(phrase_tokens))

    # Also scan full text for known multi-word state names (e.g. "New York")
    for state in us.states.STATES:
        for name in (state.name, state.abbr):
            if not name:
                continue
            if len(name) == 2 and name == state.abbr:
                if not _state_abbreviation_in_text(name, text):
                    continue
            elif not re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                continue
            candidates.append(name)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(candidate.strip())
    return deduped


def lookup_state_fips(name: str) -> str | None:
    """Return zero-padded state FIPS for a name or abbreviation."""
    if not name:
        return None
    state = us.states.lookup(name.strip())
    if state and state.fips:
        return str(state.fips).zfill(2)
    return None


def _detect_geo_level_from_keywords(text: str) -> GeographyLevel | None:
    text_l = text.lower()
    if NATIONAL_PATTERN.search(text_l):
        return "nation"
    if STATE_PATTERN.search(text_l):
        return "state"
    if COUNTY_PATTERN.search(text_l):
        return "county"
    if PLACE_PATTERN.search(text_l):
        return "place"
    if CBSA_PATTERN.search(text_l):
        return "cbsa"
    return None


def _detect_geo_level_from_suffix(text: str) -> GeographyLevel | None:
    text_l = text.lower()
    if re.search(r"\bcounty\b|\bcounties\b", text_l):
        return "county"
    if re.search(r"\bcity\b|\bcities\b|\bplace\b|\bplaces\b|\btown\b|\btowns\b", text_l):
        return "place"
    return None


def _collect_state_fips(text: str, candidates: list[str]) -> list[str]:
    fips_codes: list[str] = []
    seen: set[str] = set()

    names_to_check: list[str] = list(candidates)
    names_to_check.extend(re.findall(r"\b[A-Za-z]+\b", text))

    for name in names_to_check:
        for token in name.split():
            if token.lower() in NOISE_WORDS:
                continue
            if len(token) == 2 and token.islower() and token.lower() in AMBIGUOUS_STATE_ABBREVIATIONS:
                continue
            fips = lookup_state_fips(token)
            if fips and fips not in seen:
                seen.add(fips)
                fips_codes.append(fips)
        if name.lower() in NOISE_WORDS:
            continue
        fips = lookup_state_fips(name)
        if fips and fips not in seen:
            seen.add(fips)
            fips_codes.append(fips)

    return fips_codes


def infer_geo_context(text: str) -> DetectedGeoContext:
    """Run deterministic geo inference cascade and return typed context."""
    candidates = extract_geo_candidates(text)
    state_fips = _collect_state_fips(text, candidates)

    geo_level = _detect_geo_level_from_keywords(text)
    if geo_level is None:
        geo_level = _detect_geo_level_from_suffix(text)
    if geo_level is None and state_fips:
        geo_level = "state"

    return DetectedGeoContext(
        geo_level=geo_level,
        state_fips=state_fips,
        mapped_levels=[],
    )


def build_state_geo_ids(fips: list[str]) -> list[str]:
    """Build validated state:FIPS identifiers for BenchmarkIntent."""
    validated = DetectedGeoContext(geo_level="state", state_fips=fips)
    return [f"state:{code}" for code in validated.state_fips]
