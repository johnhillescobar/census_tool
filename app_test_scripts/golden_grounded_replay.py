"""Deterministic grounded evidence derived from committed golden Census URLs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app_test_scripts.census_url_fixtures import GoldenQuestionRow, parse_census_url
from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate, TableCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.services.grounded_census_planner import CandidateIdSelection, validate_proposed_grounded_ids
from src.services.grounded_plan_validator import GroundedPlanValidationResult, validate_grounded_plan

_GROUP = re.compile(r"^GROUP\(([^)]+)\)$", re.IGNORECASE)


@dataclass(frozen=True)
class GoldenReplay:
    """The complete evidence/selection/validation receipt for one golden row."""

    row: GoldenQuestionRow
    table_evidence: RetrievalEvidence
    geography_evidence: GeographyRetrievalResult
    validation: GroundedPlanValidationResult

    @property
    def evidence(self) -> list[RetrievalEvidence]:
        return [self.table_evidence, *self.geography_evidence.evidence]

    def fingerprint(self) -> str:
        payload = {
            "row_no": self.row.row_no,
            "evidence": [item.model_dump(mode="json") for item in self.evidence],
            "validation": self.validation.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


def canonical_geo_for(row: GoldenQuestionRow) -> dict[str, str]:
    parts = parse_census_url(row.expected_url)
    if parts.catalog_path is not None:
        return {}
    assert len(parts.geo_for) == 1, f"row {row.row_no} must have exactly one for clause"
    token, value = parts.geo_for[0]
    return {token: value or "*"}


def canonical_geo_in(row: GoldenQuestionRow) -> list[tuple[str, str]]:
    parts = parse_census_url(row.expected_url)
    return list(parts.geo_in)


def _table_code(row: GoldenQuestionRow) -> str:
    parts = parse_census_url(row.expected_url)
    variables = [item for item in parts.get_vars if item not in {"NAME", "GEO_ID"}]
    if not variables:
        # Geography-list queries still need explicit retrieved table evidence.
        return "B01001"
    match = _GROUP.fullmatch(variables[0])
    if match:
        return match.group(1).upper()
    return variables[0].split("_", 1)[0].upper()


def _evidence(evidence_id: str, collection: str, candidate) -> RetrievalEvidence:
    return RetrievalEvidence(
        evidence_id=evidence_id,
        collection_name=collection,
        status="hit",
        query_text=f"golden row {evidence_id.rsplit(':', 1)[-1]}",
        index_version="golden-replay-v1",
        schema_version="1.0",
        candidate_ids=[candidate.candidate_id],
        candidates=[candidate],
    )


def explicit_golden_proposal(
    row: GoldenQuestionRow,
    geography_evidence: GeographyRetrievalResult,
) -> CandidateIdSelection:
    """Return the grounded candidate IDs encoded in golden replay fixtures."""
    return CandidateIdSelection(
        table_id=f"golden:table:{row.row_no}",
        hierarchy_id=f"golden:hierarchy:{row.row_no}",
        area_ids=[item.candidate_ids[0] for item in geography_evidence.area_evidence],
    )


def build_golden_replay(row: GoldenQuestionRow) -> GoldenReplay | None:
    """Create official-shaped fake evidence, then validate explicit golden ID choices."""
    parts = parse_census_url(row.expected_url)
    if parts.catalog_path is not None:
        return None
    assert parts.dataset is not None and parts.year is not None

    table_code = _table_code(row)
    table = TableCandidate(
        candidate_id=f"golden:table:{row.row_no}",
        dataset=parts.dataset,
        year=parts.year,
        display_name=f"Golden table {table_code}",
        score=1.0,
        provenance="census_groups",
        schema_version="1.0",
        table_code=table_code,
        table_name=f"Golden table {table_code}",
        category="golden_replay",
        years_available=[parts.year],
    )
    table_evidence = _evidence(
        f"golden:table-evidence:{row.row_no}",
        "census_tables",
        table,
    )

    expected_for = canonical_geo_for(row)
    target_token, target_value = next(iter(expected_for.items()))
    expected_in = canonical_geo_in(row)
    parent_tokens = [token for token, _value in expected_in]
    hierarchy = HierarchyCandidate(
        candidate_id=f"golden:hierarchy:{row.row_no}",
        dataset=parts.dataset,
        year=parts.year,
        display_name=" › ".join([*parent_tokens, target_token]),
        score=1.0,
        provenance="census_geography",
        schema_version="1.0",
        friendly_level=target_token,
        census_token=target_token,
        hierarchy=" › ".join([*parent_tokens, target_token]),
        parent_census_tokens=parent_tokens,
    )
    hierarchy_evidence = _evidence(
        f"golden:hierarchy-evidence:{row.row_no}",
        "census_dataset_geographies",
        hierarchy,
    )

    area_evidence: list[RetrievalEvidence] = []
    for index, (token, value) in enumerate(expected_in):
        area = AreaCandidate(
            candidate_id=f"golden:area:{row.row_no}:parent:{index}",
            dataset=parts.dataset,
            year=parts.year,
            display_name=f"{token}:{value}",
            score=1.0,
            provenance="census_api",
            schema_version="1.0",
            friendly_level=token,
            census_token=token,
            geo_id=f"golden-parent-{row.row_no}-{index}",
            geography_code=value,
        )
        area_evidence.append(
            _evidence(
                f"golden:area-evidence:{row.row_no}:parent:{index}",
                "census_geography_areas",
                area,
            )
        )

    if target_value != "*" or target_token == "us" and target_value == "*":
        area = AreaCandidate(
            candidate_id=f"golden:area:{row.row_no}:target",
            dataset=parts.dataset,
            year=parts.year,
            display_name=f"{target_token}:{target_value}",
            score=1.0,
            provenance="census_api",
            schema_version="1.0",
            friendly_level=target_token,
            census_token=target_token,
            geo_id=f"golden-target-{row.row_no}",
            geography_code=target_value,
        )
        area_evidence.append(
            _evidence(
                f"golden:area-evidence:{row.row_no}:target",
                "census_geography_areas",
                area,
            )
        )

    geography_evidence = GeographyRetrievalResult(
        hierarchy_evidence=hierarchy_evidence,
        area_evidence=area_evidence,
    )
    proposed = explicit_golden_proposal(row, geography_evidence)
    selection = validate_proposed_grounded_ids(proposed, table_evidence, geography_evidence)
    evidence = [table_evidence, *geography_evidence.evidence]
    validation = validate_grounded_plan(selection, evidence)
    return GoldenReplay(
        row=row,
        table_evidence=table_evidence,
        geography_evidence=geography_evidence,
        validation=validation,
    )


__all__ = [
    "GoldenReplay",
    "build_golden_replay",
    "canonical_geo_for",
    "canonical_geo_in",
    "explicit_golden_proposal",
]
