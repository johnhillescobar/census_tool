from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from app_test_scripts.census_url_fixtures import load_golden_questions, parse_census_url
from src.domain.geography_catalog import (
    AreaCandidate,
    CatalogCandidate,
    IndexManifest,
)
from src.domain.geography_contract import CensusGeographyToken, GeographyIntent
from src.domain.retrieval_plan import GroundedSelection, RetrievalEvidence


def test_canonical_census_vocabulary_contains_all_golden_tokens():
    tokens = set(get_args(CensusGeographyToken))
    golden_tokens = {
        level
        for row in load_golden_questions()
        for pair in (parse_census_url(row.expected_url).geo_for, parse_census_url(row.expected_url).geo_in)
        for level, _ in pair
    }
    assert tokens == golden_tokens
    assert "tribal census tract (or part)" in tokens
    assert "american indian area/alaska native area/hawaiian home land (or part)" in tokens
    assert "zip code tabulation area" in tokens


def test_friendly_level_and_exact_census_token_are_separate():
    intent = GeographyIntent(
        level="cbsa",
        census_token="metropolitan statistical area/micropolitan statistical area (or part)",
        display_name="Los Angeles metro, California portion",
        source="explicit",
    )
    assert intent.level == "cbsa"
    assert intent.census_token.endswith("(or part)")


def test_candidates_and_manifest_round_trip_with_versions():
    candidate = AreaCandidate(
        candidate_id="geo-area:abc",
        dataset="acs/acs5",
        year=2023,
        display_name="California",
        provenance="census_api",
        schema_version="1.0",
        friendly_level="state",
        census_token="state",
        geo_id="0400000US06",
        geography_code="06",
    )
    restored = TypeAdapter(CatalogCandidate).validate_python(candidate.model_dump())
    assert restored.candidate_kind == "area"

    manifest = IndexManifest(
        collection_name="census_geography_areas",
        schema_version="1.0",
        index_version="1.0",
        built_at=datetime(2026, 7, 21, tzinfo=UTC),
        document_count=1,
    )
    assert IndexManifest.model_validate_json(manifest.model_dump_json()) == manifest


def test_retrieval_evidence_and_selection_fail_closed():
    with pytest.raises(ValidationError, match="candidate_ids"):
        RetrievalEvidence(
            evidence_id="e1",
            collection_name="census_geography_areas",
            status="hit",
            query_text="California",
        )

    with pytest.raises(ValidationError, match="selected candidate"):
        GroundedSelection(
            selection_id="s1",
            status="selected",
            evidence_ids=["e1"],
        )
