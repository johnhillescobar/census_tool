import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig

from config import LATEST_AVAILABLE_YEAR
from src.clients.telemetry import record_event
from src.domain.geography_catalog import AreaCandidate, TableCandidate
from src.domain.geography_contract import (
    ClarificationPrompt,
    GeographyClarificationRequired,
    GeographyIntent,
    GeographyResolved,
)
from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence
from src.domain.retrieval_trace import (
    RetrievalCandidateTrace,
    RetrievalStage,
    RetrievalStatus,
    RetrievalTrace,
    RetrievalTraceEvent,
)
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis, analyze_retrieval_request
from src.services.chroma_catalog_retriever import (
    GeographyRetrievalResult,
    retrieve_geography_candidates,
    retrieve_table_candidates,
)
from src.services.geography_policy import resolve_geography_intent
from src.services.grounded_census_planner import select_grounded_plan
from src.services.grounded_plan_validator import GroundedPlanValidationResult, validate_grounded_plan
from src.state.types import CensusState, FinalResponseState
from src.state.workflow_plan import WorkflowPlan
from src.workflows.graph_patch import CensusGraphPatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroundedGeographyDependencies:
    analyze: Callable[[str], CensusRetrievalAnalysis] = analyze_retrieval_request
    retrieve_tables: Callable[..., RetrievalEvidence] = retrieve_table_candidates
    retrieve_geographies: Callable[..., GeographyRetrievalResult] = retrieve_geography_candidates
    select: Callable[..., GroundedSelection] = select_grounded_plan
    validate: Callable[..., GroundedPlanValidationResult] = validate_grounded_plan


def _grounded_planning_enabled() -> bool:
    return os.getenv("CENSUS_CHROMA_GROUNDED_PLANNING", "1").strip().lower() not in {"0", "false", "no", "off"}


def _planning_year(plan: WorkflowPlan | None) -> int:
    temporal = plan.resolved_temporal_intent() if plan else None
    if temporal is None:
        return LATEST_AVAILABLE_YEAR
    return temporal.anchor_year or temporal.end_year or temporal.start_year or LATEST_AVAILABLE_YEAR


def _trace_event(
    trace: RetrievalTrace,
    stage: RetrievalStage,
    status: RetrievalStatus,
    *,
    evidence: RetrievalEvidence | None = None,
    reason_code: str | None = None,
    filters: dict[str, Any] | None = None,
    selected_ids: list[str] | None = None,
) -> None:
    event = RetrievalTraceEvent(
        stage=stage,
        status=status,
        reason_code=reason_code,
        collection=evidence.collection_name if evidence else None,
        filters=filters or {},
        candidates=[
            RetrievalCandidateTrace(
                candidate_id=candidate.candidate_id,
                score=candidate.score,
                display_name=candidate.display_name,
            )
            for candidate in (evidence.candidates if evidence else [])
        ],
        selected_ids=selected_ids or [],
        index_version=evidence.index_version if evidence else None,
    )
    trace.append(event)
    record_event(
        "grounded_retrieval",
        {
            "trace_id": trace.trace_id,
            "stage": stage.value,
            "status": status.value,
            "reason_code": reason_code,
            "collection": event.collection,
            "filters": event.filters,
            "candidate_ids": [candidate.candidate_id for candidate in event.candidates],
            "selected_ids": event.selected_ids,
        },
    )


def _clarification(
    existing: WorkflowPlan,
    trace: RetrievalTrace,
    reason_code: str,
    question: str,
    evidence: list[RetrievalEvidence],
) -> dict[str, Any]:
    trace.append(
        RetrievalTraceEvent(
            stage=RetrievalStage.CLARIFICATION,
            status=RetrievalStatus.CLARIFICATION_REQUIRED,
            reason_code=reason_code,
        )
    )
    record_event(
        "grounded_retrieval",
        {
            "trace_id": trace.trace_id,
            "stage": RetrievalStage.CLARIFICATION.value,
            "status": RetrievalStatus.CLARIFICATION_REQUIRED.value,
            "reason_code": reason_code,
        },
    )
    resolution = GeographyClarificationRequired(
        reason_code=reason_code,
        clarification_prompt=ClarificationPrompt(
            template_id="grounded_geography_clarification",
            reason_code=reason_code,
            question_text=question,
            options=[],
        ),
    )
    return CensusGraphPatch(
        plan=existing.model_copy(
            update={
                "geography": resolution,
                "retrieval_evidence": evidence,
                "retrieval_trace": trace,
                "requires_clarification": True,
            }
        ),
        final=FinalResponseState(answer_text=question),
        logs=[f"geography: grounded clarification required ({reason_code})"],
    ).as_langgraph_update()


def _legacy_geography_node(state: CensusState) -> dict[str, Any]:
    user_question = state.messages[-1]["content"]
    profile_default = state.profile.get("default_geo") if state.profile else None
    resolution = resolve_geography_intent(user_question, profile_default_geo=profile_default)
    existing = state.plan or WorkflowPlan()
    if resolution.status == "clarification_required":
        prompt = resolution.clarification_prompt
        option_lines = [f"{option.option_id}: {option.label}" for option in prompt.options]
        clarification_text = f"{prompt.question_text}\n" + "\n".join(option_lines)
        return CensusGraphPatch(
            plan=existing.model_copy(update={"geography": resolution, "requires_clarification": True}),
            final=FinalResponseState(answer_text=clarification_text),
            logs=[f"geography: legacy clarification required ({resolution.reason_code})"],
        ).as_langgraph_update()
    return CensusGraphPatch(
        plan=existing.model_copy(update={"geography": resolution, "requires_clarification": False}),
        geo=resolution.geography,
        logs=[f"geography: legacy resolved ({resolution.geography.source})"],
    ).as_langgraph_update()


def geography_node(
    state: CensusState,
    config: RunnableConfig,
    dependencies: GroundedGeographyDependencies | None = None,
) -> dict[str, Any]:
    """Build geography only from selected and validated Chroma evidence."""
    if not _grounded_planning_enabled():
        return _legacy_geography_node(state)

    user_question = state.messages[-1]["content"]
    existing = state.plan or WorkflowPlan()
    configured = config.get("configurable", {}).get("grounded_geography_dependencies")
    deps = dependencies or configured or GroundedGeographyDependencies()
    trace = RetrievalTrace(prompt_version="grounded-geography-v1")
    evidence: list[RetrievalEvidence] = []

    try:
        analysis = deps.analyze(user_question)
    except Exception as exc:
        logger.warning("Grounded request analysis failed: %s", exc)
        _trace_event(trace, RetrievalStage.ANALYSIS, RetrievalStatus.ERROR, reason_code="ANALYSIS_FAILED")
        return _clarification(existing, trace, "ANALYSIS_FAILED", "Please restate the Census topic and geography.", evidence)
    _trace_event(trace, RetrievalStage.ANALYSIS, RetrievalStatus.RESOLVED)

    requested_year = _planning_year(existing)
    table_evidence = deps.retrieve_tables(analysis, year=requested_year)
    evidence.append(table_evidence)
    table_status = RetrievalStatus.HIT if table_evidence.status == "hit" else RetrievalStatus.EMPTY
    _trace_event(
        trace,
        RetrievalStage.TABLE_RETRIEVAL,
        table_status,
        evidence=table_evidence,
        reason_code=None if table_evidence.status == "hit" else f"TABLE_{table_evidence.status.upper()}",
        filters={"year": requested_year},
    )
    if table_evidence.status != "hit":
        reason = f"TABLE_{table_evidence.status.upper()}"
        return _clarification(
            existing,
            trace,
            reason,
            "I could not ground a current Census table for that topic. Which Census measure should I use?",
            evidence,
        )

    table_selection = deps.select(table_evidence)
    if table_selection.status != "selected":
        reason = table_selection.reason_code or "TABLE_AMBIGUOUS"
        _trace_event(trace, RetrievalStage.GROUNDED_SELECTION, RetrievalStatus.REJECTED, reason_code=reason)
        return _clarification(
            existing,
            trace,
            reason,
            "More than one Census table matches that measure. Please specify the measure more precisely.",
            evidence,
        )
    selected_table = next(
        (
            candidate
            for candidate in table_evidence.candidates
            if isinstance(candidate, TableCandidate) and candidate.candidate_id == table_selection.selected_table_ids[0]
        ),
        None,
    )
    if selected_table is None:
        return _clarification(
            existing,
            trace,
            "TABLE_SELECTION_INVALID",
            "I could not validate the selected Census table. Please specify another measure.",
            evidence,
        )

    if not analysis.geography_explicit:
        return _clarification(
            existing,
            trace,
            "MISSING_EXPLICIT_GEOGRAPHY",
            "Which U.S. geography should I use? Please name a state, county, city, or national scope.",
            evidence,
        )

    geography_result = deps.retrieve_geographies(
        analysis,
        dataset=selected_table.dataset,
        year=requested_year,
    )
    evidence.extend(geography_result.evidence)
    for item in geography_result.evidence:
        status = RetrievalStatus.HIT if item.status == "hit" else RetrievalStatus.EMPTY
        _trace_event(
            trace,
            RetrievalStage.GEOGRAPHY_RETRIEVAL,
            status,
            evidence=item,
            reason_code=None if item.status == "hit" else f"GEOGRAPHY_{item.status.upper()}",
            filters={"dataset": selected_table.dataset, "year": requested_year},
        )
    unusable = next((item for item in geography_result.evidence if item.status != "hit"), None)
    if unusable is not None:
        reason = f"GEOGRAPHY_{unusable.status.upper()}"
        return _clarification(
            existing,
            trace,
            reason,
            "I could not find one current, unambiguous Census geography for that request. Please specify it more precisely.",
            evidence,
        )

    selection = deps.select(table_evidence, geography_result)
    if selection.status != "selected":
        reason = selection.reason_code or "GEOGRAPHY_AMBIGUOUS"
        _trace_event(trace, RetrievalStage.GROUNDED_SELECTION, RetrievalStatus.REJECTED, reason_code=reason)
        return _clarification(
            existing,
            trace,
            reason,
            "The requested geography is ambiguous. Please provide its state or a more specific name.",
            evidence,
        )
    _trace_event(
        trace,
        RetrievalStage.GROUNDED_SELECTION,
        RetrievalStatus.RESOLVED,
        selected_ids=[
            *selection.selected_table_ids,
            *([selection.selected_hierarchy_id] if selection.selected_hierarchy_id else []),
            *selection.selected_area_ids,
        ],
    )

    validation = deps.validate(selection, evidence)
    if validation.status != "valid" or validation.plan is None or validation.plan.geography is None:
        reason = validation.failures[0].reason_code if validation.failures else "PLAN_VALIDATION_FAILED"
        _trace_event(trace, RetrievalStage.PLAN_VALIDATION, RetrievalStatus.REJECTED, reason_code=reason)
        return _clarification(
            existing,
            trace,
            reason,
            "That geography is not valid for the selected Census table and year. Please choose a supported geography.",
            evidence,
        )

    grounded = validation.plan
    canonical_geo = grounded.geography
    hierarchy_candidate = next(
        candidate
        for candidate in geography_result.hierarchy_evidence.candidates
        if candidate.candidate_id == canonical_geo.hierarchy_candidate_id
    )
    selected_areas = [
        candidate
        for item in geography_result.area_evidence
        for candidate in item.candidates
        if isinstance(candidate, AreaCandidate) and candidate.candidate_id in canonical_geo.area_candidate_ids
    ]
    display_name = ", ".join(area.display_name for area in selected_areas) or hierarchy_candidate.display_name
    try:
        geography = GeographyIntent(
            level=hierarchy_candidate.friendly_level,
            geo_for=canonical_geo.geo_for,
            geo_in=dict(canonical_geo.geo_in),
            display_name=display_name,
            source="chroma",
            requested_text=analysis.geography_search_text,
            census_token=canonical_geo.census_token,
        )
    except ValueError:
        return _clarification(
            existing,
            trace,
            "UNSUPPORTED_GEOGRAPHY_CONTRACT",
            "That Census geography cannot be represented safely. Please choose another geography.",
            evidence,
        )
    _trace_event(trace, RetrievalStage.PLAN_VALIDATION, RetrievalStatus.RESOLVED)
    resolution = GeographyResolved(geography=geography)
    return CensusGraphPatch(
        plan=existing.model_copy(
            update={
                "geography": resolution,
                "selected_table": grounded.table,
                "retrieval_evidence": evidence,
                "grounded_plan": grounded,
                "retrieval_trace": trace,
                "requires_clarification": False,
            }
        ),
        geo=geography,
        logs=[
            f"geography: grounded resolved ({geography.source})",
            f"retrieval: {' -> '.join(trace.compact_summary())}",
        ],
    ).as_langgraph_update()


__all__ = ["GroundedGeographyDependencies", "geography_node"]
