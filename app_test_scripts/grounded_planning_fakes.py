from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.geography_catalog import AreaCandidate, HierarchyCandidate, TableCandidate
from src.domain.retrieval_plan import EvidenceStatus, RetrievalEvidence
from src.services.census_retrieval_analyzer import CensusRetrievalAnalysis, analyze_retrieval_request
from src.services.chroma_catalog_retriever import GeographyRetrievalResult
from src.services.grounded_census_planner import select_grounded_plan
from src.workflows.geography import GroundedGeographyDependencies


@dataclass
class FakeGroundedRetrieval:
    table_status: EvidenceStatus = "hit"
    geography_status: EvidenceStatus = "hit"
    calls: list[tuple[str, object]] = field(default_factory=list)

    def analyze(self, question: str) -> CensusRetrievalAnalysis:
        self.calls.append(("analyze", question))
        return analyze_retrieval_request(question)

    def retrieve_tables(self, analysis: CensusRetrievalAnalysis, *, year: int) -> RetrievalEvidence:
        self.calls.append(("table", year))
        candidate = TableCandidate(
            candidate_id="table:population",
            dataset="acs/acs5",
            year=year,
            display_name="Total Population",
            score=0.99,
            provenance="census_groups",
            schema_version="1.0",
            table_code="B01003",
            table_name="Total Population",
            category="detail",
            years_available=[year],
        )
        return RetrievalEvidence(
            evidence_id="table-evidence",
            collection_name="census_tables",
            status=self.table_status,
            query_text=analysis.table_search_text,
            index_version="1.0",
            schema_version="1.0",
            candidate_ids=[candidate.candidate_id] if self.table_status == "hit" else [],
            candidates=[candidate] if self.table_status == "hit" else [],
        )

    def retrieve_geographies(
        self,
        analysis: CensusRetrievalAnalysis,
        *,
        dataset: str,
        year: int,
    ) -> GeographyRetrievalResult:
        self.calls.append(("geography", (dataset, year)))
        hierarchy = HierarchyCandidate(
            candidate_id="hierarchy:county",
            dataset=dataset,
            year=year,
            display_name="Counties within state",
            score=0.99,
            provenance="census_geography",
            schema_version="1.0",
            friendly_level="county",
            census_token="county",
            hierarchy="state › county",
            parent_census_tokens=["state"],
        )
        area = AreaCandidate(
            candidate_id="area:california",
            dataset=dataset,
            year=year,
            display_name="California",
            score=0.99,
            provenance="census_api",
            schema_version="1.0",
            friendly_level="state",
            census_token="state",
            geo_id="0400000US06",
            geography_code="06",
        )
        hierarchy_evidence = RetrievalEvidence(
            evidence_id="hierarchy-evidence",
            collection_name="census_dataset_geographies",
            status=self.geography_status,
            query_text=analysis.geography_search_text,
            index_version="1.0",
            schema_version="1.0",
            candidate_ids=[hierarchy.candidate_id] if self.geography_status == "hit" else [],
            candidates=[hierarchy] if self.geography_status == "hit" else [],
        )
        area_evidence = RetrievalEvidence(
            evidence_id="area-evidence",
            collection_name="census_geography_areas",
            status=self.geography_status,
            query_text=analysis.area_search_texts[0] if analysis.area_search_texts else "California",
            index_version="1.0",
            schema_version="1.0",
            candidate_ids=[area.candidate_id] if self.geography_status == "hit" else [],
            candidates=[area] if self.geography_status == "hit" else [],
        )
        return GeographyRetrievalResult(
            hierarchy_evidence=hierarchy_evidence,
            area_evidence=[area_evidence],
        )

    def dependencies(self) -> GroundedGeographyDependencies:
        defaults = GroundedGeographyDependencies()
        return GroundedGeographyDependencies(
            analyze=self.analyze,
            retrieve_tables=self.retrieve_tables,
            retrieve_geographies=self.retrieve_geographies,
            select=select_grounded_plan,
            validate=defaults.validate,
        )
