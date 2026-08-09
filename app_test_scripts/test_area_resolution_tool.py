import json

import pytest
from pydantic import ValidationError

from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.agent_planning_artifacts import collect_planning_artifacts
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.tools.area_resolution_tool import AreaResolutionTool


def _hierarchy_candidate(*, candidate_id: str = "hierarchy:place") -> HierarchyCandidate:
    return HierarchyCandidate(
        candidate_id=candidate_id,
        dataset="acs/acs5",
        year=2023,
        display_name="Places within state",
        score=0.99,
        provenance="census_geography",
        schema_version="1.0",
        friendly_level="place",
        census_token="place",
        hierarchy="state › place",
        parent_census_tokens=["state"],
    )


def _area_candidate(
    *,
    candidate_id: str,
    display_name: str,
    geography_code: str,
    geo_id: str,
) -> AreaCandidate:
    return AreaCandidate(
        candidate_id=candidate_id,
        dataset="acs/acs5",
        year=2023,
        display_name=display_name,
        score=0.99,
        provenance="census_api",
        schema_version="1.0",
        friendly_level="place",
        census_token="place",
        geo_id=geo_id,
        geography_code=geography_code,
    )


def _mock_geography_result(*, area_evidence: RetrievalEvidence) -> GeographyRetrievalResult:
    hierarchy = _hierarchy_candidate()
    return GeographyRetrievalResult(
        hierarchy_evidence=RetrievalEvidence(
            evidence_id="hierarchy-evidence",
            collection_name="census_dataset_geographies",
            status="hit",
            query_text="place",
            candidate_ids=[hierarchy.candidate_id],
            candidates=[hierarchy],
        ),
        area_evidence=[area_evidence],
    )


def test_area_resolution_tool_returns_chroma_candidate(monkeypatch):
    tool = AreaResolutionTool()
    area = _area_candidate(
        candidate_id="area:nyc",
        display_name="New York city, New York",
        geography_code="51000",
        geo_id="1600000US3651000",
    )
    area_evidence = RetrievalEvidence(
        evidence_id="area-evidence",
        collection_name="census_geography_areas",
        status="hit",
        query_text="New York City",
        candidate_ids=[area.candidate_id],
        candidates=[area],
    )
    monkeypatch.setattr(
        "src.tools.area_resolution_tool.retrieve_geography_candidates",
        lambda *args, **kwargs: _mock_geography_result(area_evidence=area_evidence),
    )

    payload = {
        "name": "New York City",
        "geography_type": "place",
        "dataset": "acs/acs5",
        "year": 2023,
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["status"] == "resolved"
    assert data["code"] == "51000"
    assert data["candidate_id"] == "area:nyc"
    assert data["source"] == "chroma"
    RetrievalEvidence.model_validate(data["area_evidence"])
    RetrievalEvidence.model_validate(data["hierarchy_evidence"])


def test_area_resolution_tool_returns_ambiguous_evidence(monkeypatch):
    tool = AreaResolutionTool()
    areas = [
        _area_candidate(
            candidate_id="area:nyc",
            display_name="New York city, New York",
            geography_code="51000",
            geo_id="1600000US3651000",
        ),
        _area_candidate(
            candidate_id="area:yonkers",
            display_name="Yonkers city, New York",
            geography_code="84000",
            geo_id="1600000US3984000",
        ),
    ]
    area_evidence = RetrievalEvidence(
        evidence_id="area-evidence",
        collection_name="census_geography_areas",
        status="hit",
        query_text="New York",
        candidate_ids=[area.candidate_id for area in areas],
        candidates=areas,
    )
    monkeypatch.setattr(
        "src.tools.area_resolution_tool.retrieve_geography_candidates",
        lambda *args, **kwargs: _mock_geography_result(area_evidence=area_evidence),
    )

    output = tool._run(
        json.dumps(
            {
                "name": "New York",
                "geography_type": "place",
                "dataset": "acs/acs5",
                "year": 2023,
            }
        )
    )
    data = json.loads(output)
    assert data["status"] == "ambiguous"
    assert data["count"] == 2
    evidence = RetrievalEvidence.model_validate(data["area_evidence"])
    assert evidence.status == "hit"
    assert len(evidence.candidates) == 2
    assert "code" not in data


def test_area_resolution_tool_returns_empty_evidence(monkeypatch):
    tool = AreaResolutionTool()
    area_evidence = RetrievalEvidence(
        evidence_id="area-evidence",
        collection_name="census_geography_areas",
        status="empty",
        query_text="Mars",
    )
    monkeypatch.setattr(
        "src.tools.area_resolution_tool.retrieve_geography_candidates",
        lambda *args, **kwargs: _mock_geography_result(area_evidence=area_evidence),
    )

    output = tool._run(
        json.dumps(
            {
                "name": "Mars",
                "geography_type": "state",
                "dataset": "acs/acs5",
                "year": 2023,
            }
        )
    )
    data = json.loads(output)
    assert data["status"] == "empty"
    evidence = RetrievalEvidence.model_validate(data["area_evidence"])
    assert evidence.status == "empty"
    assert evidence.candidate_ids == []


def test_collect_planning_artifacts_ingests_area_resolution_evidence():
    area = _area_candidate(
        candidate_id="area:nyc",
        display_name="New York city, New York",
        geography_code="51000",
        geo_id="1600000US3651000",
    )
    area_evidence = RetrievalEvidence(
        evidence_id="area-evidence",
        collection_name="census_geography_areas",
        status="hit",
        query_text="New York City",
        candidate_ids=[area.candidate_id],
        candidates=[area],
    )
    hierarchy = _hierarchy_candidate()
    hierarchy_evidence = RetrievalEvidence(
        evidence_id="hierarchy-evidence",
        collection_name="census_dataset_geographies",
        status="hit",
        query_text="place",
        candidate_ids=[hierarchy.candidate_id],
        candidates=[hierarchy],
    )
    observation = json.dumps(
        {
            "status": "ambiguous",
            "count": 1,
            "source": "chroma",
            "area_evidence": area_evidence.model_dump(mode="json"),
            "hierarchy_evidence": hierarchy_evidence.model_dump(mode="json"),
        }
    )
    action = type("Action", (), {"tool": "resolve_area_name", "tool_input": "{}"})()
    collected, selection = collect_planning_artifacts([(action, observation)])
    assert selection is None
    assert {item.evidence_id for item in collected} == {"area-evidence", "hierarchy-evidence"}


def test_area_resolution_tool_rejects_invalid_evidence_shape():
    with pytest.raises(ValidationError):
        RetrievalEvidence.model_validate(
            {
                "evidence_id": "bad",
                "collection_name": "census_geography_areas",
                "status": "hit",
                "query_text": "NYC",
                "candidate_ids": [],
            }
        )
