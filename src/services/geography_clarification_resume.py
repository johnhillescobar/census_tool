"""Resume a pending geography clarification from preserved Chroma evidence."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.domain.clarification_templates import render_geography_clarification
from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate, TableCandidate
from src.domain.geography_contract import ClarificationOption, GeographyIntent, GeographyResolved
from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence
from src.services.grounded_plan_validator import validate_grounded_plan
from src.state.workflow_plan import PendingGeographyOption, WorkflowPlan

_NON_WORD = re.compile(r"[^\w]+")


class GeographyResumeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Literal["resolved", "clarification_required", "cancelled"]
    plan: WorkflowPlan
    geography: GeographyIntent | None = None
    answer_text: str = ""


def _normalized(value: str) -> str:
    return _NON_WORD.sub(" ", value.casefold()).strip()


def _render_pending(plan: WorkflowPlan, message: str | None = None) -> GeographyResumeResult:
    pending = plan.pending_geography_clarification
    if pending is None:
        raise ValueError("pending geography clarification is required")
    prompt = render_geography_clarification(
        pending.reason_code,
        [ClarificationOption(option_id=item.option_id, label=item.label) for item in pending.options],
    )
    lines = [prompt.question_text, *(f"{item.option_id}: {item.label}" for item in prompt.options)]
    if message:
        lines.insert(0, message)
    return GeographyResumeResult(
        status="clarification_required",
        plan=plan,
        answer_text="\n".join(lines),
    )


def _select_option(selection: str, options: list[PendingGeographyOption]) -> PendingGeographyOption | None:
    needle = _normalized(selection)
    exact = [
        option
        for option in options
        if needle in {_normalized(option.option_id), _normalized(option.candidate_id), _normalized(option.label)}
    ]
    if len(exact) == 1:
        return exact[0]
    contained = [option for option in options if _normalized(option.label) in needle]
    return contained[0] if len(contained) == 1 else None


def _candidate_for_option(
    option: PendingGeographyOption,
    evidence: list[RetrievalEvidence],
):
    matches = [
        candidate for item in evidence for candidate in item.candidates if candidate.candidate_id == option.candidate_id
    ]
    if len(matches) != 1 or matches[0].display_name != option.label:
        return None
    return matches[0]


def _single_candidate_id(evidence: list[RetrievalEvidence], candidate_type: type) -> str | None:
    candidates = [
        candidate.candidate_id for item in evidence for candidate in item.candidates if isinstance(candidate, candidate_type)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _selection_for_option(
    plan: WorkflowPlan,
    option: PendingGeographyOption,
) -> GroundedSelection | None:
    evidence = plan.retrieval_evidence
    chosen = _candidate_for_option(option, evidence)
    if chosen is None:
        return None

    table_id = option.candidate_id if isinstance(chosen, TableCandidate) else None
    table_id = table_id or (plan.selected_table.candidate_id if plan.selected_table else None)
    table_id = table_id or _single_candidate_id(evidence, TableCandidate)

    hierarchy_id = option.candidate_id if isinstance(chosen, HierarchyCandidate) else None
    hierarchy_id = hierarchy_id or _single_candidate_id(evidence, HierarchyCandidate)

    area_ids: list[str] = []
    for item in evidence:
        area_candidates = [candidate for candidate in item.candidates if isinstance(candidate, AreaCandidate)]
        if not area_candidates:
            continue
        if isinstance(chosen, AreaCandidate) and any(
            candidate.candidate_id == chosen.candidate_id for candidate in area_candidates
        ):
            area_ids.append(chosen.candidate_id)
        elif len(area_candidates) == 1:
            area_ids.append(area_candidates[0].candidate_id)
        else:
            return None

    if table_id is None or hierarchy_id is None:
        return None
    return GroundedSelection(
        selection_id=f"resume:{plan.pending_geography_clarification.trace_id}",
        status="selected",
        evidence_ids=[item.evidence_id for item in evidence],
        selected_table_ids=[table_id],
        selected_hierarchy_id=hierarchy_id,
        selected_area_ids=area_ids,
    )


def resume_geography_clarification(plan: WorkflowPlan, selection: str) -> GeographyResumeResult:
    """Resolve one option against the exact candidate records saved in the pending plan."""
    pending = plan.pending_geography_clarification
    if pending is None:
        raise ValueError("no pending geography clarification")
    if _normalized(selection) in {"cancel", "stop", "never mind", "nevermind"}:
        return GeographyResumeResult(
            status="cancelled",
            plan=plan.model_copy(
                update={
                    "pending_geography_clarification": None,
                    "requires_clarification": False,
                    "workflow_cancelled": True,
                }
            ),
            answer_text="Cancelled the pending geography request.",
        )

    option = _select_option(selection, pending.options)
    if option is None or option.candidate_id not in pending.retrieved_candidate_ids:
        return _render_pending(plan, "That selection does not match one of the retrieved options.")
    containing_evidence = [item for item in plan.retrieval_evidence if option.candidate_id in item.candidate_ids]
    if (
        len(containing_evidence) != 1
        or containing_evidence[0].status != "hit"
        or (pending.index_version is not None and containing_evidence[0].index_version != pending.index_version)
    ):
        return _render_pending(plan, "That retrieved option is no longer valid in the preserved evidence.")

    grounded_selection = _selection_for_option(plan, option)
    if grounded_selection is None:
        return _render_pending(plan, "That option does not complete a compatible geography selection.")
    validation = validate_grounded_plan(grounded_selection, plan.retrieval_evidence)
    if validation.status != "valid" or validation.plan is None or validation.plan.geography is None:
        return _render_pending(plan, "That option is incompatible with the preserved Census evidence.")

    grounded = validation.plan
    canonical = grounded.geography
    candidates = [candidate for item in plan.retrieval_evidence for candidate in item.candidates]
    hierarchy = next(
        candidate
        for candidate in candidates
        if isinstance(candidate, HierarchyCandidate) and candidate.candidate_id == canonical.hierarchy_candidate_id
    )
    areas = [
        candidate
        for candidate in candidates
        if isinstance(candidate, AreaCandidate) and candidate.candidate_id in canonical.area_candidate_ids
    ]
    geography = GeographyIntent(
        level=hierarchy.friendly_level,
        geo_for=canonical.geo_for,
        geo_in=dict(canonical.geo_in),
        display_name=", ".join(area.display_name for area in areas) or hierarchy.display_name,
        source="chroma",
        requested_text=pending.original_query,
        census_token=canonical.census_token,
    )
    resolved_plan = plan.model_copy(
        update={
            "geography": GeographyResolved(geography=geography),
            "selected_table": grounded.table,
            "grounded_plan": grounded,
            "pending_geography_clarification": None,
            "requires_clarification": False,
            "workflow_cancelled": False,
        }
    )
    return GeographyResumeResult(status="resolved", plan=resolved_plan, geography=geography)


__all__ = ["GeographyResumeResult", "resume_geography_clarification"]
