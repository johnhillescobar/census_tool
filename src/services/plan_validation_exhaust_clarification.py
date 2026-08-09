"""Build agent clarification state when plan validation retries exhaust (CENSUS-50)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate, TableCandidate
from src.domain.retrieval_plan import RetrievalEvidence, ValidationFailure
from src.domain.retrieval_trace import RetrievalStage, RetrievalStatus, RetrievalTrace, RetrievalTraceEvent
from src.services.geography_clarification_resume import (
    GeographyResumeResult,
    _selection_for_option,
    _validate_resume_option_by_candidate_id,
    render_pending_clarification_retry,
)
from src.state.workflow_plan import (
    GeographyClarificationSlot,
    PendingGeographyClarification,
    PendingGeographyOption,
    WorkflowPlan,
)

PLAN_VALIDATION_EXHAUST_PREFIX = "PLAN_VALIDATION_EXHAUST"


def is_plan_validation_exhaust_pending(pending: PendingGeographyClarification | None) -> bool:
    return pending is not None and pending.clarification_origin == "plan_validation_exhaust"


def _resolve_clarification_slot(failures: list[ValidationFailure]) -> GeographyClarificationSlot:
    if not failures:
        return "geography"

    primary = failures[0]
    field_path = primary.field_path or ""
    reason = primary.reason_code

    if field_path.startswith("selected_table") or (
        reason in {"UNKNOWN_CANDIDATE_ID", "TABLE_SELECTION_COUNT", "TABLE_GEOGRAPHY_INCOMPATIBLE"}
        and "table" in field_path
    ):
        return "table"
    if field_path.startswith("selected_hierarchy") or reason == "HIERARCHY_SELECTION_REQUIRED":
        return "hierarchy"
    if field_path.startswith("selected_area") or reason in {
        "PARENT_GEOGRAPHY_INCOMPLETE",
        "AREA_GEOGRAPHY_INCOMPATIBLE",
    }:
        return "area"
    if reason == "UNKNOWN_EVIDENCE_ID":
        return "geography"
    if reason == "UNKNOWN_CANDIDATE_ID" and primary.candidate_id:
        if primary.candidate_id.startswith("table:"):
            return "table"
        if primary.candidate_id.startswith("area:"):
            return "area"
        if primary.candidate_id.startswith("hierarchy:"):
            return "hierarchy"
    return "geography"


def _candidate_types_for_slot(slot: GeographyClarificationSlot) -> tuple[type, ...]:
    if slot == "table":
        return (TableCandidate,)
    if slot == "area":
        return (AreaCandidate,)
    if slot == "hierarchy":
        return (HierarchyCandidate,)
    return (AreaCandidate,)


def _build_pending_options(
    evidence: list[RetrievalEvidence],
    slot: GeographyClarificationSlot,
    failures: list[ValidationFailure],
) -> list[PendingGeographyOption]:
    candidate_types = _candidate_types_for_slot(slot)
    retrieved = [
        candidate
        for item in evidence
        if item.status == "hit"
        for candidate in item.candidates
        if isinstance(candidate, candidate_types)
    ]

    failure_candidate_ids = {failure.candidate_id for failure in failures if failure.candidate_id}
    if failure_candidate_ids:
        related = [candidate for candidate in retrieved if candidate.candidate_id not in failure_candidate_ids]
        if related:
            retrieved = related

    option_prefix = "table" if slot == "table" else "geo"
    return [
        PendingGeographyOption(
            option_id=f"{option_prefix}_{index}",
            candidate_id=candidate.candidate_id,
            label=candidate.display_name,
        )
        for index, candidate in enumerate(retrieved)
    ]


def prepare_plan_validation_exhaust_clarification(
    plan: WorkflowPlan,
    *,
    original_query: str,
) -> dict[str, Any]:
    """Populate pending clarification from preserved retrieval evidence after validator exhaust."""

    failures = list(plan.plan_validation_failures)
    evidence = list(plan.retrieval_evidence)
    trace = plan.retrieval_trace or RetrievalTrace(prompt_version="plan-validation-exhaust-v1")
    slot = _resolve_clarification_slot(failures)
    pending_options = _build_pending_options(evidence, slot, failures)

    primary_reason = failures[0].reason_code if failures else "PLAN_VALIDATION_FAILED"
    reason_code = f"{PLAN_VALIDATION_EXHAUST_PREFIX}_{primary_reason}"
    option_candidate_ids = {option.candidate_id for option in pending_options}
    relevant_evidence = [
        item
        for item in evidence
        if not option_candidate_ids or any(candidate_id in item.candidate_ids for candidate_id in option_candidate_ids)
    ]
    option_versions = {item.index_version for item in relevant_evidence if item.index_version is not None}
    index_version = next(iter(option_versions)) if len(option_versions) == 1 else None

    trace.append(
        RetrievalTraceEvent(
            stage=RetrievalStage.CLARIFICATION,
            status=RetrievalStatus.CLARIFICATION_REQUIRED,
            reason_code=reason_code,
        )
    )

    pending = PendingGeographyClarification(
        original_query=original_query,
        trace_id=trace.trace_id,
        retrieved_candidate_ids=[option.candidate_id for option in pending_options],
        options=pending_options,
        requested_slot=slot,
        index_version=index_version,
        reason_code=reason_code,
        clarification_origin="plan_validation_exhaust",
    )
    updated_plan = plan.model_copy(
        update={
            "pending_geography_clarification": pending,
            "requires_clarification": True,
            "proposed_selection": None,
            "retrieval_evidence": evidence,
            "retrieval_trace": trace,
            "workflow_cancelled": False,
        }
    )
    return {
        "plan": updated_plan,
        "logs": [
            f"plan_validation_exhaust: clarification required ({reason_code})",
            "plan_validation_exhaust: deferred clarification copy to agent_planning",
        ],
    }


@dataclass(frozen=True)
class PlanValidationExhaustResumePrepared:
    plan: WorkflowPlan


def apply_plan_validation_exhaust_selection(
    plan: WorkflowPlan,
    candidate_id: str,
) -> GeographyResumeResult | PlanValidationExhaustResumePrepared:
    """Map a grounded clarification choice back into a validator-bound proposal."""

    pending = plan.pending_geography_clarification
    if pending is None or not is_plan_validation_exhaust_pending(pending):
        raise ValueError("plan validation exhaust resume requires pending clarification context")

    validated = _validate_resume_option_by_candidate_id(plan, candidate_id)
    if isinstance(validated, GeographyResumeResult):
        return validated

    selection = _selection_for_option(plan, validated)
    if selection is None:
        return render_pending_clarification_retry(
            plan,
            "That option does not complete a compatible grounded selection from the preserved evidence.",
        )

    updated_plan = plan.model_copy(
        update={
            "proposed_selection": selection,
            "pending_geography_clarification": None,
            "requires_clarification": False,
            "plan_validation_failures": [],
            "plan_validation_attempts": 0,
            "workflow_cancelled": False,
        }
    )
    return PlanValidationExhaustResumePrepared(plan=updated_plan)


__all__ = [
    "PLAN_VALIDATION_EXHAUST_PREFIX",
    "PlanValidationExhaustResumePrepared",
    "apply_plan_validation_exhaust_selection",
    "is_plan_validation_exhaust_pending",
    "prepare_plan_validation_exhaust_clarification",
]
