"""Validator harness gate after agent planning (CENSUS-41 Phase 2)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from src.clients.telemetry import record_event
from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate
from src.domain.geography_contract import (
    CensusGeographyToken,
    GeographyIntent,
    GeographyLevel,
    GeographyResolved,
)
from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence, ValidationFailure
from src.domain.retrieval_trace import (
    RetrievalStage,
    RetrievalStatus,
    RetrievalTrace,
    RetrievalTraceEvent,
)
from src.services.grounded_plan_validator import (
    GroundedPlanValidationResult,
    ValidatedGroundedPlan,
    validate_grounded_plan,
)
from src.state.types import CensusState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch

logger = logging.getLogger(__name__)

MAX_PLAN_VALIDATION_ATTEMPTS = 2
_RETRYABLE_REASON_CODES = frozenset(
    {
        "UNKNOWN_CANDIDATE_ID",
        "TABLE_SELECTION_COUNT",
        "HIERARCHY_SELECTION_REQUIRED",
        "PARENT_GEOGRAPHY_INCOMPLETE",
        "TABLE_GEOGRAPHY_INCOMPATIBLE",
        "AREA_GEOGRAPHY_INCOMPATIBLE",
        "CANDIDATE_KIND_MISMATCH",
        "DUPLICATE_SELECTION_ID",
        "DUPLICATE_GEOGRAPHY_TOKEN",
    }
)


@dataclass(frozen=True)
class PlanValidatorDependencies:
    validate: Callable[..., GroundedPlanValidationResult] = validate_grounded_plan


def _trace_event(
    trace: RetrievalTrace,
    status: RetrievalStatus,
    *,
    reason_code: str | None = None,
    selected_ids: list[str] | None = None,
) -> None:
    event = RetrievalTraceEvent(
        stage=RetrievalStage.PLAN_VALIDATION,
        status=status,
        reason_code=reason_code,
        selected_ids=selected_ids or [],
    )
    trace.append(event)
    record_event(
        "grounded_retrieval",
        {
            "trace_id": trace.trace_id,
            "stage": RetrievalStage.PLAN_VALIDATION.value,
            "status": status.value,
            "reason_code": reason_code,
            "selected_ids": event.selected_ids,
        },
    )


def _retryable_failures(failures: list[ValidationFailure]) -> list[ValidationFailure]:
    return [
        failure.model_copy(update={"retryable": failure.reason_code in _RETRYABLE_REASON_CODES})
        for failure in failures
    ]


def _geography_intent_from_validated(
    grounded: ValidatedGroundedPlan,
    evidence: list[RetrievalEvidence],
    *,
    requested_text: str | None = None,
) -> GeographyIntent | None:
    canonical_geo = grounded.geography
    if canonical_geo is None:
        return None

    hierarchy_candidate = next(
        (
            candidate
            for item in evidence
            for candidate in item.candidates
            if isinstance(candidate, HierarchyCandidate)
            and candidate.candidate_id == canonical_geo.hierarchy_candidate_id
        ),
        None,
    )
    if hierarchy_candidate is None:
        return None

    selected_areas = [
        candidate
        for item in evidence
        for candidate in item.candidates
        if isinstance(candidate, AreaCandidate) and candidate.candidate_id in canonical_geo.area_candidate_ids
    ]
    display_name = ", ".join(area.display_name for area in selected_areas) or hierarchy_candidate.display_name
    try:
        return GeographyIntent(
            level=cast(GeographyLevel, hierarchy_candidate.friendly_level),
            geo_for=canonical_geo.geo_for,
            geo_in=dict(canonical_geo.geo_in),
            display_name=display_name,
            source="chroma",
            requested_text=requested_text,
            census_token=cast(CensusGeographyToken, canonical_geo.census_token),
        )
    except ValueError:
        return None


def _apply_validated_plan(
    existing: WorkflowPlan,
    selection: GroundedSelection,
    validation: GroundedPlanValidationResult,
    evidence: list[RetrievalEvidence],
    trace: RetrievalTrace,
) -> dict[str, Any]:
    grounded = validation.plan
    assert grounded is not None
    geography = _geography_intent_from_validated(grounded, evidence)
    if grounded.geography is not None and geography is None:
        _trace_event(trace, RetrievalStatus.REJECTED, reason_code="UNSUPPORTED_GEOGRAPHY_CONTRACT")
        failures = [
            ValidationFailure(
                reason_code="UNSUPPORTED_GEOGRAPHY_CONTRACT",
                message="Validated geography could not be projected into GeographyIntent",
                retryable=True,
            )
        ]
        return CensusGraphPatch(
            plan=existing.model_copy(
                update={
                    "plan_validation_failures": failures,
                    "plan_validation_attempts": existing.plan_validation_attempts + 1,
                    "proposed_selection": None,
                }
            ),
            logs=["plan_validator: rejected (unsupported geography contract)"],
        ).as_langgraph_update()

    _trace_event(
        trace,
        RetrievalStatus.RESOLVED,
        selected_ids=[
            *selection.selected_table_ids,
            *([selection.selected_hierarchy_id] if selection.selected_hierarchy_id else []),
            *selection.selected_area_ids,
        ],
    )
    plan_update: dict[str, Any] = {
        "selected_table": grounded.table,
        "retrieval_evidence": evidence,
        "grounded_plan": grounded,
        "retrieval_trace": trace,
        "proposed_selection": None,
        "plan_validation_failures": [],
        "requires_clarification": False,
        "workflow_cancelled": False,
        "pending_geography_clarification": None,
    }
    geo: GeographyIntent | None = None
    if geography is not None:
        plan_update["geography"] = GeographyResolved(geography=geography)
        geo = geography

    return CensusGraphPatch(
        plan=existing.model_copy(update=plan_update),
        geo=geo,
        logs=[
            "plan_validator: grounded plan validated",
            f"retrieval: {' -> '.join(trace.compact_summary())}",
        ],
    ).as_langgraph_update()


def validate_grounded_plan_node(
    state: CensusState,
    config: RunnableConfig,
    dependencies: PlanValidatorDependencies | None = None,
) -> dict[str, Any]:
    """Validate agent-proposed candidate IDs against attached retrieval evidence."""
    existing = state.plan or WorkflowPlan()
    configured = config.get("configurable", {}).get("plan_validator_dependencies")
    deps = dependencies or configured or PlanValidatorDependencies()

    if existing.requires_clarification:
        return {"logs": ["plan_validator: skipped (clarification required)"]}

    if existing.proposed_selection is None:
        return {"logs": ["plan_validator: skipped (no agent proposal)"]}

    selection = existing.proposed_selection
    evidence = list(existing.retrieval_evidence)
    trace = existing.retrieval_trace or RetrievalTrace(prompt_version="plan-validator-v1")

    if not evidence:
        failures = [
            ValidationFailure(
                reason_code="EVIDENCE_MISSING",
                message="Agent proposal requires attached retrieval evidence before validation",
                retryable=True,
            )
        ]
        _trace_event(trace, RetrievalStatus.REJECTED, reason_code="EVIDENCE_MISSING")
        return CensusGraphPatch(
            plan=existing.model_copy(
                update={
                    "plan_validation_failures": failures,
                    "plan_validation_attempts": existing.plan_validation_attempts + 1,
                    "proposed_selection": None,
                }
            ),
            logs=["plan_validator: rejected (missing evidence)"],
        ).as_langgraph_update()

    validation = deps.validate(selection, evidence)
    if validation.status == "valid" and validation.plan is not None:
        return _apply_validated_plan(existing, selection, validation, evidence, trace)

    failures = _retryable_failures(list(validation.failures))
    reason = failures[0].reason_code if failures else "PLAN_VALIDATION_FAILED"
    _trace_event(trace, RetrievalStatus.REJECTED, reason_code=reason)
    logger.info("plan_validator: rejected agent proposal (%s)", reason)
    return CensusGraphPatch(
        plan=existing.model_copy(
            update={
                "plan_validation_failures": failures,
                "plan_validation_attempts": existing.plan_validation_attempts + 1,
                "retrieval_trace": trace,
                "proposed_selection": None,
            }
        ),
        logs=[f"plan_validator: rejected ({reason})"],
    ).as_langgraph_update()


__all__ = ["MAX_PLAN_VALIDATION_ATTEMPTS", "PlanValidatorDependencies", "validate_grounded_plan_node"]
