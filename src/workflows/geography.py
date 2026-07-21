import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig

from config import LATEST_AVAILABLE_YEAR
from src.clients.telemetry import record_event
from src.domain.clarification_templates import (
    normalize_geography_reason,
    render_geography_clarification,
)
from src.domain.geography_catalog import AreaCandidate, TableCandidate
from src.domain.geography_contract import (
    ClarificationOption,
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
from src.services.geography_clarification_resume import resume_geography_clarification
from src.services.grounded_census_planner import select_grounded_plan
from src.services.grounded_plan_validator import GroundedPlanValidationResult, validate_grounded_plan
from src.state.types import CensusState, FinalResponseState
from src.state.workflow_plan import (
    GeographyClarificationSlot,
    PendingGeographyClarification,
    PendingGeographyOption,
    WorkflowPlan,
)
from src.workflows.graph_patch import CensusGraphPatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroundedGeographyDependencies:
    analyze: Callable[[str], CensusRetrievalAnalysis] = analyze_retrieval_request
    retrieve_tables: Callable[..., RetrievalEvidence] = retrieve_table_candidates
    retrieve_geographies: Callable[..., GeographyRetrievalResult] = retrieve_geography_candidates
    select: Callable[..., GroundedSelection] = select_grounded_plan
    validate: Callable[..., GroundedPlanValidationResult] = validate_grounded_plan


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
    evidence: list[RetrievalEvidence],
    *,
    original_query: str,
    requested_slot: GeographyClarificationSlot,
) -> dict[str, Any]:
    normalized_reason = normalize_geography_reason(reason_code)
    candidate_types: tuple[type, ...]
    if requested_slot == "table":
        candidate_types = (TableCandidate,)
    elif requested_slot == "area":
        candidate_types = (AreaCandidate,)
    elif requested_slot == "hierarchy":
        from src.domain.geography_catalog import HierarchyCandidate

        candidate_types = (HierarchyCandidate,)
    else:
        candidate_types = (AreaCandidate,)
    retrieved = [
        candidate
        for item in evidence
        if item.status == "hit"
        for candidate in item.candidates
        if isinstance(candidate, candidate_types)
    ]
    pending_options = [
        PendingGeographyOption(
            option_id=f"geo_{index}",
            candidate_id=candidate.candidate_id,
            label=candidate.display_name,
        )
        for index, candidate in enumerate(retrieved)
    ]
    prompt = render_geography_clarification(
        normalized_reason,
        [ClarificationOption(option_id=option.option_id, label=option.label) for option in pending_options],
    )
    clarification_text = "\n".join(
        [prompt.question_text, *(f"{option.option_id}: {option.label}" for option in prompt.options)]
    )
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
            reason_code=normalized_reason,
        )
    )
    record_event(
        "grounded_retrieval",
        {
            "trace_id": trace.trace_id,
            "stage": RetrievalStage.CLARIFICATION.value,
            "status": RetrievalStatus.CLARIFICATION_REQUIRED.value,
            "reason_code": normalized_reason,
        },
    )
    resolution = GeographyClarificationRequired(
        reason_code=normalized_reason,
        clarification_prompt=prompt,
    )
    pending = PendingGeographyClarification(
        original_query=original_query,
        trace_id=trace.trace_id,
        retrieved_candidate_ids=[option.candidate_id for option in pending_options],
        options=pending_options,
        requested_slot=requested_slot,
        index_version=index_version,
        reason_code=normalized_reason,
    )
    return CensusGraphPatch(
        plan=existing.model_copy(
            update={
                "geography": resolution,
                "retrieval_evidence": evidence,
                "retrieval_trace": trace,
                "pending_geography_clarification": pending,
                "requires_clarification": True,
                "workflow_cancelled": False,
            }
        ),
        final=FinalResponseState(
            answer_text=clarification_text,
            clarification_type="geography",
            reason_code=normalized_reason,
            trace_id=trace.trace_id,
        ),
        logs=[f"geography: grounded clarification required ({normalized_reason})"],
    ).as_langgraph_update()


def geography_node(
    state: CensusState,
    config: RunnableConfig,
    dependencies: GroundedGeographyDependencies | None = None,
) -> dict[str, Any]:
    """Build geography only from selected and validated Chroma evidence."""
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
        return _clarification(
            existing,
            trace,
            "ANALYSIS_FAILED",
            evidence,
            original_query=user_question,
            requested_slot="geography",
        )
    _trace_event(trace, RetrievalStage.ANALYSIS, RetrievalStatus.RESOLVED)
    if not analysis.geography_explicit and state.profile:
        saved = state.profile.get("default_geo")
        saved_display = saved.get("display_name") if isinstance(saved, dict) else None
        profile_hint = saved_display or state.profile.get("last_geo")
        if isinstance(profile_hint, str) and profile_hint.strip():
            preferred_level = state.profile.get("preferred_level")
            level_hint = preferred_level if isinstance(preferred_level, str) else "geography"
            analysis = analysis.model_copy(
                update={
                    "geography_search_text": f"{level_hint} {profile_hint}".strip(),
                    "area_search_texts": [profile_hint],
                    "geography_explicit": True,
                }
            )

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
            evidence,
            original_query=user_question,
            requested_slot="table",
        )

    table_selection = deps.select(table_evidence)
    if table_selection.status != "selected":
        reason = table_selection.reason_code or "TABLE_AMBIGUOUS"
        _trace_event(trace, RetrievalStage.GROUNDED_SELECTION, RetrievalStatus.REJECTED, reason_code=reason)
        return _clarification(
            existing,
            trace,
            reason,
            evidence,
            original_query=user_question,
            requested_slot="table",
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
            evidence,
            original_query=user_question,
            requested_slot="table",
        )

    if not analysis.geography_explicit:
        return _clarification(
            existing,
            trace,
            "MISSING_EXPLICIT_GEOGRAPHY",
            evidence,
            original_query=user_question,
            requested_slot="geography",
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
            evidence,
            original_query=user_question,
            requested_slot="geography",
        )

    selection = deps.select(table_evidence, geography_result)
    if selection.status != "selected":
        reason = selection.reason_code or "GEOGRAPHY_AMBIGUOUS"
        _trace_event(trace, RetrievalStage.GROUNDED_SELECTION, RetrievalStatus.REJECTED, reason_code=reason)
        requested_slot: GeographyClarificationSlot = "geography"
        if len(geography_result.hierarchy_evidence.candidates) > 1:
            requested_slot = "hierarchy"
        elif any(len(item.candidates) > 1 for item in geography_result.area_evidence):
            requested_slot = "area"
        return _clarification(
            existing,
            trace,
            reason,
            evidence,
            original_query=user_question,
            requested_slot=requested_slot,
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
            evidence,
            original_query=user_question,
            requested_slot="geography",
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
            evidence,
            original_query=user_question,
            requested_slot="geography",
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
                "pending_geography_clarification": None,
                "requires_clarification": False,
                "workflow_cancelled": False,
            }
        ),
        geo=geography,
        logs=[
            f"geography: grounded resolved ({geography.source})",
            f"retrieval: {' -> '.join(trace.compact_summary())}",
        ],
    ).as_langgraph_update()


def geography_resume_node(state: CensusState, config: RunnableConfig) -> dict[str, Any]:
    """Resume a checkpointed geography choice without reinterpreting it as a new query."""
    plan = state.plan
    if plan is None or plan.pending_geography_clarification is None:
        raise ValueError("geography resume requires pending clarification context")
    pending = plan.pending_geography_clarification
    selection = state.messages[-1]["content"]
    result = resume_geography_clarification(plan, selection)
    if result.status == "resolved":
        return CensusGraphPatch(
            plan=result.plan,
            geo=result.geography,
            logs=[f"geography: resumed from trace {pending.trace_id}"],
        ).as_langgraph_update()
    reason_code = "GEOGRAPHY_CANCELLED" if result.status == "cancelled" else pending.reason_code
    return CensusGraphPatch(
        plan=result.plan,
        final=FinalResponseState(
            answer_text=result.answer_text,
            clarification_type="geography",
            reason_code=reason_code,
            trace_id=pending.trace_id,
        ),
        logs=[f"geography: clarification {result.status} ({reason_code})"],
    ).as_langgraph_update()


__all__ = ["GroundedGeographyDependencies", "geography_node", "geography_resume_node"]
