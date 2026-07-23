"""Validation and canonical materialization of candidate-ID selections."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate, TableCandidate
from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence, ValidationFailure


class CanonicalTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    dataset: str
    year: int
    table_code: str
    table_name: str
    category: str
    years_available: list[int] = Field(default_factory=list)


class CanonicalGeography(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hierarchy_candidate_id: str
    area_candidate_ids: list[str] = Field(default_factory=list)
    dataset: str
    year: int
    census_token: str
    hierarchy: str
    geo_for: dict[str, str]
    geo_in: list[tuple[str, str]] = Field(default_factory=list)


class ValidatedGroundedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: str
    evidence_ids: list[str]
    table: CanonicalTable
    geography: CanonicalGeography | None = None


class GroundedPlanValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "invalid"]
    plan: ValidatedGroundedPlan | None = None
    failures: list[ValidationFailure] = Field(default_factory=list)

    @model_validator(mode="after")
    def result_shape_matches_status(self) -> GroundedPlanValidationResult:
        if self.status == "valid" and (self.plan is None or self.failures):
            raise ValueError("valid result requires a plan and no failures")
        if self.status == "invalid" and (self.plan is not None or not self.failures):
            raise ValueError("invalid result requires failures and no plan")
        return self


def _failure(
    reason_code: str,
    message: str,
    *,
    candidate_id: str | None = None,
    evidence_id: str | None = None,
    field_path: str | None = None,
) -> GroundedPlanValidationResult:
    return GroundedPlanValidationResult(
        status="invalid",
        failures=[
            ValidationFailure(
                reason_code=reason_code,
                message=message,
                candidate_id=candidate_id,
                evidence_id=evidence_id,
                field_path=field_path,
            )
        ],
    )


def validate_grounded_plan(
    selection: GroundedSelection,
    evidence: Iterable[RetrievalEvidence],
) -> GroundedPlanValidationResult:
    """Reject unknown IDs, then materialize canonical values exclusively from evidence."""
    evidence_items = list(evidence)
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    if selection.status != "selected":
        return _failure("SELECTION_NOT_SELECTED", "Only a selected plan can be validated")
    if len(evidence_by_id) != len(evidence_items):
        return _failure("DUPLICATE_EVIDENCE_ID", "Evidence IDs must be unique")
    if set(selection.evidence_ids) != set(evidence_by_id):
        unknown = next((item for item in selection.evidence_ids if item not in evidence_by_id), None)
        return _failure(
            "UNKNOWN_EVIDENCE_ID",
            "Selection evidence IDs do not exactly match supplied evidence",
            evidence_id=unknown,
            field_path="evidence_ids",
        )
    if any(item.status != "hit" for item in evidence_items):
        item = next(item for item in evidence_items if item.status != "hit")
        return _failure(
            "EVIDENCE_NOT_USABLE",
            f"Evidence status is {item.status}",
            evidence_id=item.evidence_id,
        )

    candidates = [candidate for item in evidence_items for candidate in item.candidates]
    counts = Counter(candidate.candidate_id for candidate in candidates)
    duplicate = next((candidate_id for candidate_id, count in counts.items() if count > 1), None)
    if duplicate:
        return _failure("DUPLICATE_CANDIDATE_ID", "Candidate ID is not unique in evidence", candidate_id=duplicate)
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    selected_ids = [
        *selection.selected_table_ids,
        *([selection.selected_hierarchy_id] if selection.selected_hierarchy_id else []),
        *selection.selected_area_ids,
    ]
    unknown = next((candidate_id for candidate_id in selected_ids if candidate_id not in candidate_by_id), None)
    if unknown is not None:
        return _failure(
            "UNKNOWN_CANDIDATE_ID",
            "Selected candidate ID was not supplied by retrieval evidence",
            candidate_id=unknown,
        )
    if len(selected_ids) != len(set(selected_ids)):
        return _failure("DUPLICATE_SELECTION_ID", "A candidate ID was selected more than once")
    if len(selection.selected_table_ids) != 1:
        return _failure("TABLE_SELECTION_COUNT", "Exactly one table candidate must be selected")

    table_candidate = candidate_by_id[selection.selected_table_ids[0]]
    if not isinstance(table_candidate, TableCandidate):
        return _failure(
            "CANDIDATE_KIND_MISMATCH",
            "Selected table ID does not identify a table",
            candidate_id=table_candidate.candidate_id,
        )
    canonical_table = CanonicalTable(
        candidate_id=table_candidate.candidate_id,
        dataset=table_candidate.dataset,
        year=table_candidate.year,
        table_code=table_candidate.table_code,
        table_name=table_candidate.table_name,
        category=table_candidate.category,
        years_available=table_candidate.years_available,
    )

    if selection.selected_hierarchy_id is None:
        if selection.selected_area_ids:
            return _failure("HIERARCHY_SELECTION_REQUIRED", "Area selections require hierarchy evidence")
        return GroundedPlanValidationResult(
            status="valid",
            plan=ValidatedGroundedPlan(
                selection_id=selection.selection_id,
                evidence_ids=selection.evidence_ids,
                table=canonical_table,
            ),
        )

    hierarchy = candidate_by_id[selection.selected_hierarchy_id]
    if not isinstance(hierarchy, HierarchyCandidate):
        return _failure(
            "CANDIDATE_KIND_MISMATCH",
            "Selected hierarchy ID does not identify a hierarchy",
            candidate_id=hierarchy.candidate_id,
        )
    areas = [candidate_by_id[candidate_id] for candidate_id in selection.selected_area_ids]
    non_area = next((candidate for candidate in areas if not isinstance(candidate, AreaCandidate)), None)
    if non_area is not None:
        return _failure(
            "CANDIDATE_KIND_MISMATCH",
            "Selected area ID does not identify an area",
            candidate_id=non_area.candidate_id,
        )
    typed_areas = [candidate for candidate in areas if isinstance(candidate, AreaCandidate)]
    token_counts = Counter(area.census_token for area in typed_areas)
    duplicate_token = next((token for token, count in token_counts.items() if count > 1), None)
    if duplicate_token is not None:
        return _failure(
            "DUPLICATE_GEOGRAPHY_TOKEN",
            f"Multiple selected areas use geography token {duplicate_token}",
            field_path="selected_area_ids",
        )

    compatible_year = hierarchy.year in table_candidate.years_available
    if table_candidate.dataset != hierarchy.dataset or not compatible_year:
        return _failure(
            "TABLE_GEOGRAPHY_INCOMPATIBLE",
            "Table and hierarchy dataset/year partitions are incompatible",
            candidate_id=hierarchy.candidate_id,
        )
    incompatible_area = next(
        (area for area in typed_areas if area.dataset != hierarchy.dataset or area.year != hierarchy.year),
        None,
    )
    if incompatible_area is not None:
        return _failure(
            "AREA_GEOGRAPHY_INCOMPATIBLE",
            "Area and hierarchy dataset/year partitions are incompatible",
            candidate_id=incompatible_area.candidate_id,
        )

    areas_by_token = {area.census_token: area for area in typed_areas}
    missing = [token for token in hierarchy.parent_census_tokens if token not in areas_by_token]
    if missing:
        return _failure(
            "PARENT_GEOGRAPHY_INCOMPLETE",
            f"Missing required parent geography: {', '.join(missing)}",
            candidate_id=hierarchy.candidate_id,
            field_path="selected_area_ids",
        )

    target_area = areas_by_token.get(hierarchy.census_token)
    if hierarchy.census_token == "us":
        geo_for = {"us": target_area.geography_code if target_area else "1"}
    else:
        geo_for = {hierarchy.census_token: target_area.geography_code if target_area else "*"}
    geo_in = [(token, areas_by_token[token].geography_code) for token in hierarchy.parent_census_tokens]
    canonical_geography = CanonicalGeography(
        hierarchy_candidate_id=hierarchy.candidate_id,
        area_candidate_ids=selection.selected_area_ids,
        dataset=hierarchy.dataset,
        year=hierarchy.year,
        census_token=hierarchy.census_token,
        hierarchy=hierarchy.hierarchy,
        geo_for=geo_for,
        geo_in=geo_in,
    )
    return GroundedPlanValidationResult(
        status="valid",
        plan=ValidatedGroundedPlan(
            selection_id=selection.selection_id,
            evidence_ids=selection.evidence_ids,
            table=canonical_table,
            geography=canonical_geography,
        ),
    )


__all__ = [
    "CanonicalGeography",
    "CanonicalTable",
    "GroundedPlanValidationResult",
    "ValidatedGroundedPlan",
    "validate_grounded_plan",
]
