import json

from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate
from src.domain.retrieval_plan import RetrievalEvidence
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.tools.area_resolution_tool import AreaResolutionTool


def test_area_resolution_tool_returns_chroma_candidate(monkeypatch):
    tool = AreaResolutionTool()
    hierarchy = HierarchyCandidate(
        candidate_id="hierarchy:place",
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
    area = AreaCandidate(
        candidate_id="area:nyc",
        dataset="acs/acs5",
        year=2023,
        display_name="New York city, New York",
        score=0.99,
        provenance="census_api",
        schema_version="1.0",
        friendly_level="place",
        census_token="place",
        geo_id="1600000US3651000",
        geography_code="51000",
    )

    monkeypatch.setattr(
        "src.tools.area_resolution_tool.retrieve_geography_candidates",
        lambda *args, **kwargs: GeographyRetrievalResult(
            hierarchy_evidence=RetrievalEvidence(
                evidence_id="hierarchy-evidence",
                collection_name="census_dataset_geographies",
                status="hit",
                query_text="place",
                candidate_ids=[hierarchy.candidate_id],
                candidates=[hierarchy],
            ),
            area_evidence=[
                RetrievalEvidence(
                    evidence_id="area-evidence",
                    collection_name="census_geography_areas",
                    status="hit",
                    query_text="New York City",
                    candidate_ids=[area.candidate_id],
                    candidates=[area],
                )
            ],
        ),
    )

    payload = {
        "name": "New York City",
        "geography_type": "place",
        "dataset": "acs/acs5",
        "year": 2023,
    }
    output = tool._run(json.dumps(payload))
    data = json.loads(output)
    assert data["code"] == "51000"
    assert data["candidate_id"] == "area:nyc"
    assert data["source"] == "chroma"
