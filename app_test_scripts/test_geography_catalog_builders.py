import json
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from config import CENSUS_CATALOG_SCHEMA_VERSION
from index.build_geography_areas_index import (
    AreaPartition,
    area_metadata,
    fetch_area_rows,
    stable_area_id,
    upsert_area_rows,
    write_area_manifest,
)
from index.build_geography_index import (
    ExampleRow,
    parse_geography_table,
    stable_geography_id,
    summarize_geography_levels,
)
from index.build_index_table import CensusTableIndexBuilder, stable_table_id
from index.check_geography_index import check_index_health
from src.domain.geography_catalog import IndexManifest


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return [
            ["NAME", "GEO_ID", "state"],
            ["California", "0400000US06", "06"],
        ]


class FakeHttpClient:
    def __init__(self):
        self.call = None

    def get(self, url, *, params, timeout):
        self.call = (url, params, timeout)
        return FakeResponse()


class FakeCollection:
    metadata = {
        "schema_version": "1.0",
        "index_version": "1.0",
    }

    def __init__(self):
        self.upserts = []

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    def count(self):
        return sum(len(call["ids"]) for call in self.upserts)


class FakeClient:
    def __init__(self):
        self.collection = FakeCollection()

    def get_or_create_collection(self, *args, **kwargs):
        return self.collection

    def get_collection(self, _name):
        return self.collection


def test_authoritative_geography_rows_are_enriched_by_examples():
    html = """
    <table>
      <tr>
        <th>Reference Date</th><th>Geography Level</th>
        <th>Geography Hierarchy</th><th>Limit</th>
      </tr>
      <tr><td>2023-01-01</td><td>050</td><td>state › county</td><td></td></tr>
      <tr><td>2023-01-01</td><td>155</td><td>state › place › county (or part)</td><td></td></tr>
    </table>
    """
    table = BeautifulSoup(html, "html.parser").find("table")
    rows = parse_geography_table(
        "detail",
        "acs/acs5",
        2023,
        table,
        "https://api.census.gov/data/2023/acs/acs5/geography.html",
    )
    examples = [
        ExampleRow(
            category="detail",
            dataset="acs/acs5",
            year=2023,
            geography_hierarchy="state › place › county (or part)",
            geography_level="155",
            example_url="https://api.census.gov/example",
            notes=[],
        )
    ]
    docs = summarize_geography_levels(rows, examples)
    payload = next(payload for payload in docs.values() if payload["hierarchy"] == "state › place › county (or part)")
    assert payload["census_token"] == "county (or part)"
    assert payload["friendly_level"] == "county"
    assert payload["summary_level"] == "155"
    assert payload["example_urls"] == ["https://api.census.gov/example"]
    assert payload["candidate_id"] == stable_geography_id(
        "acs/acs5",
        2023,
        "state › place › county (or part)",
        "county (or part)",
    )


def test_area_enumeration_metadata_batching_and_manifest_are_offline(tmp_path: Path):
    http = FakeHttpClient()
    rows = fetch_area_rows(
        "acs/acs5",
        2023,
        "state",
        AreaPartition(),
        http_client=http,
    )
    assert http.call[1] == {"get": "NAME,GEO_ID", "for": "state:*"}
    assert stable_area_id(rows[0]) == stable_area_id(rows[0])
    metadata = area_metadata(rows[0])
    assert metadata["schema_version"] == CENSUS_CATALOG_SCHEMA_VERSION
    assert all(isinstance(value, str | int | float | bool) for value in metadata.values())

    client = FakeClient()
    assert upsert_area_rows(client, rows * 2, batch_size=1) == 1
    assert client.collection.upserts[0]["ids"] == [stable_area_id(rows[0])]

    path = tmp_path / "manifest.json"
    manifest = write_area_manifest(
        path,
        rows=rows * 2,
        source_urls=["https://api.census.gov/data/2023/acs/acs5"],
    )
    assert IndexManifest.model_validate_json(path.read_text()) == manifest
    assert manifest.document_count == 1


def test_table_index_metadata_has_grounding_fields():
    builder = object.__new__(CensusTableIndexBuilder)
    builder.collection = FakeCollection()
    builder.upsert_to_chroma(
        {
            "acs/acs5:B01003": {
                "table_code": "B01003",
                "table_name": "Total Population",
                "dataset": "acs/acs5",
                "years_available": [2023],
            }
        }
    )
    metadata = builder.collection.upserts[0]["metadatas"][0]
    expected_id = stable_table_id("acs/acs5", "B01003")
    assert builder.collection.upserts[0]["ids"] == [expected_id]
    assert metadata["candidate_id"] == expected_id
    assert metadata["provenance"] == "census_groups"
    assert metadata["source_url"] == "https://api.census.gov/data/2023/acs/acs5/groups.json"
    assert metadata["schema_version"] == CENSUS_CATALOG_SCHEMA_VERSION
    assert json.loads(json.dumps(metadata)) == metadata


def test_health_check_validates_manifest_age_and_count(tmp_path: Path):
    client = FakeClient()
    client.collection.upsert(ids=["one"], documents=["doc"], metadatas=[{"ok": True}])
    manifest = IndexManifest(
        collection_name="census_geography_areas",
        schema_version="1.0",
        index_version="1.0",
        built_at=datetime(2026, 7, 21, tzinfo=UTC),
        document_count=1,
    )
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")

    healthy = check_index_health(
        client,
        "census_geography_areas",
        path,
        now=datetime(2026, 7, 21, 1, tzinfo=UTC),
    )
    assert healthy.healthy is True

    stale = check_index_health(
        client,
        "census_geography_areas",
        path,
        max_age_seconds=1,
        now=datetime(2026, 7, 22, tzinfo=UTC),
    )
    assert stale.reason == "stale"
