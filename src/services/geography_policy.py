"""Deterministic geography planning policy."""

from __future__ import annotations

import re

import us

from src.domain.geo_utils import GEOGRAPHY_MAPPINGS, resolve_geography_hint
from src.domain.geography_contract import (
    ClarificationOption,
    ClarificationPrompt,
    GeographyClarificationRequired,
    GeographyIntent,
    GeographyResolution,
    GeographyResolved,
)
from src.services.benchmark_geo_inference import (
    NATIONAL_PATTERN,
    extract_geo_candidates,
    infer_geo_context,
    lookup_mapped_level,
)

AMBIGUOUS_PLACE_PATTERN = re.compile(r"\b(springfield|portland|arlington|franklin|washington)\b", re.IGNORECASE)
INVALID_GEO_PATTERN = re.compile(r"\bmars\b", re.IGNORECASE)

US_NATIONAL_GEO = GeographyIntent(
    level="nation",
    geo_for={"us": "1"},
    geo_in={},
    display_name="United States",
    source="missing_geo_default",
)


def _clarification(reason_code: str, question: str, options: list[tuple[str, str]]) -> GeographyClarificationRequired:
    return GeographyClarificationRequired(
        reason_code=reason_code,
        clarification_prompt=ClarificationPrompt(
            template_id=f"geography.{reason_code.lower()}.v1",
            reason_code=reason_code,
            question_text=question,
            options=[ClarificationOption(option_id=option_id, label=label) for option_id, label in options],
        ),
    )


def _profile_default_to_intent(
    profile_default_geo: dict,
    *,
    requested_text: str,
) -> GeographyIntent | None:
    """Convert saved profile default_geo JSON into a typed GeographyIntent."""
    if not profile_default_geo.get("level"):
        return None

    level = profile_default_geo.get("level")
    if level not in {"nation", "state", "county", "place", "cbsa"}:
        return None

    geo_for = dict(profile_default_geo.get("geo_for") or {})
    geo_in = dict(profile_default_geo.get("geo_in") or {})
    filters = profile_default_geo.get("filters") or {}
    if not geo_for and isinstance(filters, dict):
        for_clause = filters.get("for")
        in_clause = filters.get("in")
        if isinstance(for_clause, str):
            for segment in for_clause.split():
                token, _, value = segment.partition(":")
                if token and value:
                    geo_for[token] = value
        if isinstance(in_clause, str):
            for segment in in_clause.split():
                token, _, value = segment.partition(":")
                if token and value:
                    geo_in[token] = value

    if not geo_for:
        return None

    display_name = (
        profile_default_geo.get("display_name")
        or profile_default_geo.get("note")
        or profile_default_geo.get("name")
        or str(level)
    )
    return GeographyIntent(
        level=level,  # type: ignore[arg-type]
        geo_for=geo_for,
        geo_in=geo_in,
        display_name=str(display_name),
        source="profile_default",
        requested_text=requested_text,
    )


def _mapping_to_intent(mapping: dict, *, source: str, requested_text: str | None) -> GeographyIntent:
    level = mapping["level"]
    if level not in {"nation", "state", "county", "place", "cbsa"}:
        level = "place"
    return GeographyIntent(
        level=level,  # type: ignore[arg-type]
        geo_for=dict(mapping.get("geo_for") or {}),
        geo_in=dict(mapping.get("geo_in") or {}),
        display_name=mapping.get("note") or mapping["level"],
        source=source,  # type: ignore[arg-type]
        requested_text=requested_text,
    )


def _resolve_explicit_candidate(candidate: str, *, requested_text: str) -> GeographyIntent | None:
    hint = resolve_geography_hint(candidate, profile_default_geo=None)
    if hint.get("level") in {"tract", "block_group"}:
        return None
    if hint.get("geo_for") or hint.get("filters"):
        return _mapping_to_intent(hint, source="explicit", requested_text=requested_text)
    return None


def resolve_geography_intent(
    text: str,
    *,
    profile_default_geo: dict | None = None,
) -> GeographyResolution:
    """Resolve geography deterministically before temporal/benchmark planning."""
    requested_text = text or ""

    if INVALID_GEO_PATTERN.search(requested_text):
        return _clarification(
            "GEOGRAPHY_NOT_FOUND",
            "The geography you requested is not available in U.S. Census data. "
            "Please specify a valid U.S. geography (state, county, city, etc.).",
            [("retry", "Try another geography"), ("cancel", "Cancel")],
        )

    if NATIONAL_PATTERN.search(requested_text):
        explicit = GeographyIntent(
            level="nation",
            geo_for={"us": "1"},
            geo_in={},
            display_name="United States",
            source="explicit",
            requested_text=requested_text,
        )
        return GeographyResolved(geography=explicit)

    candidates = extract_geo_candidates(requested_text)
    resolved_candidates: list[GeographyIntent] = []
    for candidate in candidates:
        if candidate.lower() in {"compare", "vs", "versus", "against"}:
            continue
        mapped = lookup_mapped_level(candidate)
        if mapped and candidate.lower() in GEOGRAPHY_MAPPINGS:
            mapping = GEOGRAPHY_MAPPINGS[candidate.lower()]
            resolved_candidates.append(_mapping_to_intent(mapping, source="explicit", requested_text=requested_text))
            continue
        explicit = _resolve_explicit_candidate(candidate, requested_text=requested_text)
        if explicit is not None:
            resolved_candidates.append(explicit)

    ctx = infer_geo_context(requested_text)
    if ctx.state_fips and not resolved_candidates:
        fips = ctx.state_fips[0]
        state = us.states.lookup(fips)
        name = state.name if state else f"State {fips}"
        return GeographyResolved(
            geography=GeographyIntent(
                level="state",
                geo_for={"state": fips},
                geo_in={},
                display_name=name,
                source="explicit",
                requested_text=requested_text,
            )
        )

    if len(resolved_candidates) > 1:
        return _clarification(
            "GEOGRAPHY_AMBIGUOUS",
            "I found multiple geographies in your request. Which one should I use?",
            [(f"geo_{idx}", item.display_name) for idx, item in enumerate(resolved_candidates[:4])],
        )

    if len(resolved_candidates) == 1:
        return GeographyResolved(geography=resolved_candidates[0])

    if AMBIGUOUS_PLACE_PATTERN.search(requested_text) and not ctx.state_fips:
        return _clarification(
            "GEOGRAPHY_AMBIGUOUS",
            "That place name is ambiguous. Please specify the state or county context.",
            [("clarify", "Add state or county"), ("cancel", "Cancel")],
        )

    if profile_default_geo:
        profile_intent = _profile_default_to_intent(
            profile_default_geo,
            requested_text=requested_text,
        )
        if profile_intent is not None:
            return GeographyResolved(geography=profile_intent)

    # Locked policy: missing geography defaults to United States national scope.
    default_geo = US_NATIONAL_GEO.model_copy(update={"requested_text": requested_text})
    return GeographyResolved(geography=default_geo)
