import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from bs4 import BeautifulSoup, Tag

from config import CENSUS_CATALOG_SCHEMA_VERSION
from index.build_geography_areas_index import (
    NATIONAL_LEVELS,
    STATE_PARENT_LEVELS,
    AreaPartition,
    AreaRow,
    area_metadata,
    build_areas_index,
    ensure_areas_collection,
    fetch_area_rows,
    iter_default_area_jobs,
    load_progress,
    stable_area_id,
    upsert_area_rows,
    write_area_manifest,
)
from index.build_geography_index import (
    ExampleRow,
    datasets_for_year_range,
    parse_geography_table,
    stable_geography_id,
    summarize_geography_levels,
    upsert_geography_levels,
)
from index.build_index_table import CensusTableIndexBuilder, stable_table_id, write_table_manifest
from index.table_metadata import enrich_table_info, infer_breadth, infer_primary_topic
from index.check_geography_index import ACTIVE_CATALOG_COLLECTIONS, check_index_health
from index.rebuild_catalog import (
    _resolve_components,
    collections_built_by_components,
    missing_active_collections,
)
from src.domain.census_groups import CensusGroupsAPI
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
        self.call: tuple[str, dict[str, str], int] | None = None

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
        self.deleted: list[str] = []
        self.created: list[str] = []
        self._has_collection = True

    def get_or_create_collection(self, *args, **kwargs):
        return self.collection

    def get_collection(self, name):
        if not self._has_collection:
            raise ValueError(f"missing collection {name}")
        return self.collection

    def delete_collection(self, name):
        self.deleted.append(name)
        self._has_collection = False

    def create_collection(self, name, metadata=None, embedding_function=None, **_kwargs):
        self.created.append(name)
        self._has_collection = True
        self.collection = FakeCollection()
        self.collection.metadata = metadata or FakeCollection.metadata
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
    assert isinstance(table, Tag)
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


def test_area_enumeration_metadata_batching_and_manifest_are_offline(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CENSUS_API_KEY", "test-key")

    http = FakeHttpClient()
    rows = fetch_area_rows(
        "acs/acs5",
        2023,
        "state",
        AreaPartition(),
        http_client=http,
    )
    assert http.call is not None
    assert http.call[1] == {"get": "NAME,GEO_ID", "for": "state:*", "key": "test-key"}
    assert stable_area_id(rows[0]) == stable_area_id(rows[0])
    metadata = area_metadata(rows[0])
    assert metadata["schema_version"] == CENSUS_CATALOG_SCHEMA_VERSION
    assert all(isinstance(value, str | int | float | bool) for value in metadata.values())

    client = FakeClient()
    assert upsert_area_rows(cast(Any, client), rows * 2, batch_size=1) == 1
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
    collection = FakeCollection()
    builder.collection = cast(Any, collection)
    builder.upsert_to_chroma(
        {
            "acs/acs5:B01003": {
                "table_code": "B01003",
                "table_name": "Total Population",
                "dataset": "acs/acs5",
                "category": "detail",
                "years_available": [2023],
                "data_types": ["population"],
            }
        }
    )
    metadata = collection.upserts[0]["metadatas"][0]
    expected_id = stable_table_id("acs/acs5", "B01003")
    assert collection.upserts[0]["ids"] == [expected_id]
    assert metadata["candidate_id"] == expected_id
    assert metadata["provenance"] == "census_groups"
    assert metadata["source_url"] == "https://api.census.gov/data/2023/acs/acs5/groups.json"
    assert metadata["schema_version"] == CENSUS_CATALOG_SCHEMA_VERSION
    assert metadata["year"] == 2023
    assert metadata["years_available"] == "2023"
    assert metadata["primary_topic"] == "population"
    assert metadata["breadth"] == "broad"
    assert metadata["universe"] == "Total Population"
    assert json.loads(json.dumps(metadata)) == metadata


def test_table_metadata_distinguishes_population_from_housing():
    population = enrich_table_info(
        {
            "table_code": "B01003",
            "table_name": "Total Population",
            "category": "detail",
        }
    )
    housing = enrich_table_info(
        {
            "table_code": "B25003",
            "table_name": "Tenure",
            "category": "detail",
        }
    )
    assert population["primary_topic"] == "population"
    assert population["breadth"] == "broad"
    assert housing["primary_topic"] == "housing"
    assert housing["breadth"] == "detailed"
    assert infer_primary_topic("B01001", "Sex by Age") == "population"
    assert infer_breadth("B01001", "Sex by Age", "detail") == "detailed"


def test_table_builder_delete_recreates_and_writes_manifest(tmp_path: Path):
    client = FakeClient()

    class FakeGroupsAPI:
        def aggregate_all_categories_across_years(self, *, year_start, year_end):
            assert year_start == 2014
            assert year_end == 2024
            return {
                "acs/acs5:B01003": {
                    "table_code": "B01003",
                    "table_name": "Total Population",
                    "description": "Total Population",
                    "category": "detail",
                    "dataset": "acs/acs5",
                    "years_available": [2014, 2023, 2024],
                    "uses_groups": False,
                    "data_types": ["population"],
                }
            }

    builder = CensusTableIndexBuilder(
        persist_dir=tmp_path,
        embedding_function=object(),
        groups_api=cast(Any, FakeGroupsAPI()),
        client=cast(Any, client),
    )
    count = builder.build_index(year_start=2014, year_end=2024, delete_existing=True)
    assert count == 1
    assert client.deleted == ["census_tables"]
    assert client.created == ["census_tables"]
    assert "built_at" in (client.collection.metadata or {})
    manifest_path = tmp_path / "census_tables.manifest.json"
    manifest = IndexManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert manifest.collection_name == "census_tables"
    assert manifest.document_count == 1
    assert 2023 in manifest.years
    assert manifest.datasets == ["acs/acs5"]


def test_aggregate_all_categories_across_years_merges_years(monkeypatch):
    api = CensusGroupsAPI()
    calls: list[tuple[str, int]] = []

    def fake_fetch(dataset, year):
        calls.append((dataset, year))
        if dataset != "acs/acs5":
            return []
        if year == 2014:
            return [{"name": "B01003", "description": "Total Population"}]
        if year == 2015:
            return [
                {"name": "B01003", "description": "Total Population"},
                {"name": "B19013", "description": "Median Household Income"},
            ]
        return []

    monkeypatch.setattr(api, "fetch_groups_list", fake_fetch)
    monkeypatch.setattr(
        "src.domain.census_groups.CENSUS_CATEGORIES",
        {
            "detail": {
                "path": "acs/acs5",
                "uses_groups": False,
                "years": [2014, 2015],
            }
        },
    )
    tables = api.aggregate_all_categories_across_years(year_start=2014, year_end=2015)
    assert tables["acs/acs5:B01003"]["years_available"] == [2014, 2015]
    assert tables["acs/acs5:B19013"]["years_available"] == [2015]
    assert tables["acs/acs5:B01003"]["category"] == "detail"
    assert ("acs/acs5", 2014) in calls
    assert ("acs/acs5", 2015) in calls


def test_rebuild_catalog_components_default_to_tables_only_resolution():
    assert _resolve_components(["tables"]) == ["tables"]
    assert _resolve_components(["geographies"]) == ["geographies"]
    assert _resolve_components(["areas"]) == ["areas"]
    assert _resolve_components(["tables", "geographies"]) == ["tables", "geographies"]
    assert _resolve_components(["all"]) == ["tables", "geographies", "areas"]
    assert _resolve_components([]) == ["tables", "geographies", "areas"]


def test_iter_default_area_jobs_option2_matrix_counts():
    jobs = iter_default_area_jobs(year_start=2023, year_end=2023)
    state_count = 51
    per_year = len(NATIONAL_LEVELS) + (len(STATE_PARENT_LEVELS) * state_count)
    assert per_year == 361
    assert len(jobs) == per_year
    assert all(job.dataset == "acs/acs5" for job in jobs)
    assert {job.year for job in jobs} == {2023}
    assert "tract" not in {job.census_token for job in jobs}
    assert "block group" not in {job.census_token for job in jobs}

    two_years = iter_default_area_jobs(year_start=2022, year_end=2023)
    assert len(two_years) == per_year * 2
    assert {job.year for job in two_years} == {2022, 2023}


def test_ensure_areas_collection_deletes_and_recreates():
    client = FakeClient()
    collection = ensure_areas_collection(
        cast(Any, client),
        delete_existing=True,
        embedding_function=object(),
    )
    assert client.deleted == ["census_geography_areas"]
    assert client.created == ["census_geography_areas"]
    assert "built_at" in (collection.metadata or {})


def test_build_areas_index_resume_skips_completed_progress_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CENSUS_API_KEY", "test-key")

    state_file = tmp_path / "states.json"
    state_file.write_text(json.dumps(["state:06"]), encoding="utf-8")
    progress_path = tmp_path / "census_geography_areas.progress.json"
    completed_key = "acs/acs5|2023|us|all"
    progress_path.write_text(
        json.dumps(
            {
                "completed": [completed_key],
                "failures": [],
                "datasets": ["acs/acs5"],
                "years": [2023],
                "partitions": ["all"],
                "source_urls": ["https://api.census.gov/data/2023/acs/acs5"],
            }
        ),
        encoding="utf-8",
    )

    fetched_keys: list[str] = []

    def fake_fetch(dataset, year, census_token, partition, *, http_client=None):
        key = f"{dataset}|{year}|{census_token}|{partition.label}"
        fetched_keys.append(key)
        return [
            AreaRow(
                name=f"{census_token}-name",
                geo_id=f"GID-{census_token}",
                geography_code="06",
                census_token=census_token,
                dataset=dataset,
                year=year,
                partition=partition,
            )
        ]

    monkeypatch.setattr("index.build_geography_areas_index.fetch_area_rows", fake_fetch)

    client = FakeClient()
    count = build_areas_index(
        tmp_path,
        year_start=2023,
        year_end=2023,
        delete_existing=False,
        resume=True,
        include_tracts=False,
        include_block_groups=False,
        state_partition_file=state_file,
        progress_path=progress_path,
        failures_path=tmp_path / "failures.json",
        manifest_path=tmp_path / "manifest.json",
        client=cast(Any, client),
        embedding_function=object(),
    )
    assert completed_key not in fetched_keys
    assert count >= 1
    progress = load_progress(progress_path)
    assert completed_key in progress["completed"]
    assert len(progress["completed"]) > 1


def test_datasets_for_year_range_intersects_configured_years():
    selected = datasets_for_year_range(
        [("acs/acs5", [2012, 2014, 2023, 2024]), ("acs/acs5/subject", [2013])],
        year_start=2014,
        year_end=2023,
    )
    assert selected == [("acs/acs5", [2014, 2023])]


def test_upsert_geography_levels_deletes_and_recreates_collection():
    client = FakeClient()
    docs = {
        "geo-level:demo": {
            "candidate_id": "geo-level:demo",
            "category": "detail",
            "dataset": "acs/acs5",
            "year": 2023,
            "hierarchy": "state › county",
            "census_token": "county",
            "friendly_level": "county",
            "summary_level": "050",
            "aliases": ["county"],
            "source_url": "https://api.census.gov/data/2023/acs/acs5/geography.html",
            "example_urls": [],
        }
    }
    count = upsert_geography_levels(
        cast(Any, client),
        docs,
        delete_existing=True,
        embedding_function=object(),
    )
    assert count == 1
    assert client.deleted == ["census_dataset_geographies"]
    assert client.created == ["census_dataset_geographies"]
    assert "built_at" in (client.collection.metadata or {})
    assert client.collection.upserts[0]["ids"] == ["geo-level:demo"]
    assert client.collection.upserts[0]["metadatas"][0]["display_name"] == "state › county"


def test_load_progress_treats_empty_or_invalid_file_as_fresh(tmp_path: Path):
    empty = tmp_path / "empty.progress.json"
    empty.write_text("", encoding="utf-8")
    assert load_progress(empty) == {
        "completed": [],
        "failures": [],
        "datasets": [],
        "years": [],
        "partitions": [],
        "source_urls": [],
    }

    invalid = tmp_path / "bad.progress.json"
    invalid.write_text("{not-json", encoding="utf-8")
    assert load_progress(invalid)["completed"] == []


def test_save_progress_falls_back_when_replace_denied(tmp_path: Path, monkeypatch):
    from index.build_geography_areas_index import save_progress

    path = tmp_path / "census_geography_areas.progress.json"
    path.write_text('{"completed": []}', encoding="utf-8")

    def deny_replace(src, dst):
        raise PermissionError("Access is denied")

    monkeypatch.setattr("index.build_geography_areas_index.os.replace", deny_replace)
    monkeypatch.setattr("index.build_geography_areas_index.time.sleep", lambda _seconds: None)

    payload = {
        "completed": ["acs/acs5|2023|us|all"],
        "failures": [],
        "datasets": ["acs/acs5"],
        "years": [2023],
        "partitions": ["all"],
        "source_urls": ["https://api.census.gov/data/2023/acs/acs5"],
    }
    save_progress(path, payload)
    assert json.loads(path.read_text(encoding="utf-8"))["completed"] == ["acs/acs5|2023|us|all"]
    assert list(tmp_path.glob("*.tmp")) == []


def test_promote_copy_targets_only_collections_not_rebuilt():
    built = collections_built_by_components(["tables", "geographies"])
    assert built == {"census_tables", "census_dataset_geographies"}
    assert missing_active_collections(built) == ["census_geography_areas"]
    assert missing_active_collections(collections_built_by_components(["geographies"])) == [
        "census_tables",
        "census_geography_areas",
    ]


def test_write_table_manifest_counts_unique_years(tmp_path: Path):
    path = tmp_path / "census_tables.manifest.json"
    manifest = write_table_manifest(
        path,
        document_count=1,
        tables={
            "acs/acs5:B01003": {
                "dataset": "acs/acs5",
                "years_available": [2014, 2023],
            }
        },
    )
    assert manifest.years == [2014, 2023]
    assert IndexManifest.model_validate_json(path.read_text(encoding="utf-8")) == manifest


def test_active_catalog_collections_include_tables():
    assert "census_tables" in ACTIVE_CATALOG_COLLECTIONS


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
        cast(Any, client),
        "census_geography_areas",
        path,
        now=datetime(2026, 7, 21, 1, tzinfo=UTC),
    )
    assert healthy.healthy is True

    stale = check_index_health(
        cast(Any, client),
        "census_geography_areas",
        path,
        max_age_seconds=1,
        now=datetime(2026, 7, 22, tzinfo=UTC),
    )
    assert stale.reason == "stale"
