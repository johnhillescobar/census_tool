"""Readable turn-1 clarification copy with grounded recommended default (CENSUS-44)."""

from __future__ import annotations

from src.domain.agent_clarification_context import AgentClarificationContext
from src.domain.clarification_templates import render_slot_clarification
from src.domain.geography_catalog import TableCandidate
from src.domain.geography_contract import ClarificationOption
from src.state.workflow_plan import PendingGeographyOption


def _candidate_scores(ctx: AgentClarificationContext) -> dict[str, float]:
    scores: dict[str, float] = {}
    for item in ctx.retrieval_evidence:
        for candidate in item.candidates:
            if candidate.score is not None:
                scores[candidate.candidate_id] = candidate.score
    return scores


def recommend_default_option(ctx: AgentClarificationContext) -> PendingGeographyOption:
    """Pick the highest-scoring grounded option from preserved retrieval evidence."""
    if not ctx.pending_options:
        raise ValueError("clarification context has no pending options")
    scores = _candidate_scores(ctx)
    return max(ctx.pending_options, key=lambda option: scores.get(option.candidate_id, -1.0))


def format_readable_option_label(option: PendingGeographyOption, ctx: AgentClarificationContext) -> str:
    for item in ctx.retrieval_evidence:
        for candidate in item.candidates:
            if candidate.candidate_id != option.candidate_id:
                continue
            if isinstance(candidate, TableCandidate):
                return f"{option.label} ({candidate.table_code})"
            return option.label
    return option.label


def build_agent_clarification_copy(ctx: AgentClarificationContext) -> str:
    """Deterministic clarification message: readable labels + recommended default."""
    prompt = render_slot_clarification(
        ctx.reason_code,
        [ClarificationOption(option_id=option.option_id, label=option.label) for option in ctx.pending_options],
        requested_slot=ctx.requested_slot,
    )
    default = recommend_default_option(ctx)
    default_label = format_readable_option_label(default, ctx)

    lines = [
        prompt.question_text,
        "",
        "Available options:",
    ]
    for option in ctx.pending_options:
        readable = format_readable_option_label(option, ctx)
        suffix = " - recommended" if option.option_id == default.option_id else ""
        lines.append(f"- {readable}{suffix}")

    lines.extend(
        [
            "",
            f"Recommended default: {default_label}.",
            "Reply with the option name or confirm the recommended default to proceed.",
        ]
    )
    return "\n".join(lines)


def format_clarification_options_for_writer(ctx: AgentClarificationContext) -> str:
    default = recommend_default_option(ctx)
    lines: list[str] = []
    for option in ctx.pending_options:
        readable = format_readable_option_label(option, ctx)
        marker = " (recommended)" if option.option_id == default.option_id else ""
        lines.append(f"- {readable}{marker}")
    return "\n".join(lines)


__all__ = [
    "build_agent_clarification_copy",
    "format_clarification_options_for_writer",
    "format_readable_option_label",
    "recommend_default_option",
]
