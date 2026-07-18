import re

from src.domain.clarification_templates import (
    TemporalExplicitVsRollingSlots,
    render_temporal_clarification,
)
from src.domain.temporal_contract import (
    TemporalClarificationRequired,
    TemporalIntent,
    TemporalResolution,
    TemporalResolved,
)

EXPLICIT_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
ROLLING_PATTERN = re.compile(r"\b(last|past)\s+(\d+)\s+years?\b", re.IGNORECASE)


def _extract_explicit_years(text: str) -> list[int]:
    """Extract the explicit years from the text.

    Args:
        text: The text to extract the explicit years from.

    Returns:
        A list of explicit years.
    """
    return [int(y) for y in EXPLICIT_YEAR_PATTERN.findall(text or "")]


def _extract_rolling_phrase(text: str) -> str | None:
    """Extract the rolling phrase from the text.

    Args:
        text: The text to extract the rolling phrase from.

    Returns:
        A string representing the rolling phrase.
    """
    match = ROLLING_PATTERN.search(text or "")

    if not match:
        return None

    return f"{match.group(1).lower()} {match.group(2)} years"


def resolve_temporal_intent(user_text: str) -> TemporalResolution:
    """Resolve the temporal intent.

    Args:
        intent: The temporal intent to resolve.

    Returns:
        A TemporalResolution object.
    """

    text = user_text or ""
    years = _extract_explicit_years(text)
    rolling_phrase = _extract_rolling_phrase(text)

    # Global ambiguity policy: conflicting valid temporal interpretations => clarification
    if rolling_phrase and len(years) >= 2:
        y1, y2 = sorted(years[:2])
        clarification = render_temporal_clarification(
            TemporalExplicitVsRollingSlots(
                reason_code="TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
                year_a=y1,
                year_b=y2,
                window_text=rolling_phrase,
            )
        )
        return TemporalClarificationRequired(
            status="clarification_required",
            reason_code="TEMPORAL_CONFLICT_EXPLICIT_VS_ROLLING",
            clarification_prompt=clarification,
        )

    # Locked default: no temporal phrase => latest_available
    if not years and not rolling_phrase:
        return TemporalResolved(
            status="resolved",
            time=TemporalIntent(
                mode="latest_available",
                start_year=None,
                end_year=None,
                anchor_year=None,
                missing_year_policy="skip_with_note",
                requested_text=text,
            ),
        )

    # Explicit range
    if len(years) >= 2:
        y1, y2 = sorted(years[:2])
        return TemporalResolved(
            status="resolved",
            time=TemporalIntent(
                mode="range",
                start_year=y1,
                end_year=y2,
                anchor_year=None,
                missing_year_policy="skip_with_note",
                requested_text=text,
            ),
        )

    if len(years) == 1:
        return TemporalResolved(
            status="resolved",
            time=TemporalIntent(
                mode="point_in_time",
                start_year=None,
                end_year=None,
                anchor_year=years[0],
                missing_year_policy="skip_with_note",
                requested_text=text,
            ),
        )

    return TemporalResolved(
        status="resolved",
        time=TemporalIntent(
            mode="rolling",
            start_year=None,
            end_year=None,
            anchor_year=None,
            missing_year_policy="skip_with_note",
            requested_text=text,
        ),
    )
