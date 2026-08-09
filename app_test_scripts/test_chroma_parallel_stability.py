import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from src.clients import chroma_utils
from src.tools.area_resolution_tool import AreaResolutionTool
from src.tools.geography_discovery_tool import GeographyDiscoveryTool
from src.tools.table_catalog_retrieval_tool import TableCatalogRetrievalTool


class FakeCollection:
    def __init__(self, payload: dict | None = None, *, metadata: dict | None = None):
        self._payload = payload or {}
        self.metadata = metadata or {
            "schema_version": "1.0",
            "index_version": "1.0",
            "built_at": datetime.now(UTC).isoformat(),
        }

    def query(self, **kwargs):
        return self._payload

    def get(self, **kwargs):
        return self._payload


class CountingClient:
    init_count = 0

    def __init__(self, collection: FakeCollection | None = None, **kwargs):
        CountingClient.init_count += 1
        self._collection = collection or FakeCollection()

    def get_collection(self, name):
        return self._collection


def _hierarchy_hit_payload():
    metadata = {
        "candidate_id": "hierarchy:county",
        "dataset": "acs/acs5",
        "year": 2023,
        "geography_hierarchy": "state › county",
        "friendly_level": "county",
        "census_token": "county",
        "parent_census_tokens": '["state", "cbsa"]',
        "provenance": "census_geography",
        "schema_version": "1.0",
        "example_urls": '["for=county:*&in=state:06"]',
    }
    return {
        "ids": [["hierarchy:county"]],
        "metadatas": [[metadata]],
        "documents": [["doc"]],
        "distances": [[0.1]],
    }


@pytest.fixture(autouse=True)
def reset_chroma_singleton():
    chroma_utils.reset_chroma_client()
    CountingClient.init_count = 0
    yield
    chroma_utils.reset_chroma_client()
    CountingClient.init_count = 0


def test_initialize_chroma_client_is_process_singleton(monkeypatch):
    monkeypatch.setattr(chroma_utils.chromadb, "PersistentClient", CountingClient)

    first = chroma_utils.initialize_chroma_client()
    second = chroma_utils.initialize_chroma_client()

    assert first is second
    assert CountingClient.init_count == 1


def test_parallel_initialize_chroma_client_shares_one_client(monkeypatch):
    monkeypatch.setattr(chroma_utils.chromadb, "PersistentClient", CountingClient)

    with ThreadPoolExecutor(max_workers=4) as pool:
        clients = list(pool.map(lambda _: chroma_utils.initialize_chroma_client(), range(8)))

    assert CountingClient.init_count == 1
    assert all(client is clients[0] for client in clients)


def test_get_hierarchy_ordering_uses_dataset_geographies(monkeypatch):
    collection = FakeCollection(_hierarchy_hit_payload())
    monkeypatch.setattr(chroma_utils.chromadb, "PersistentClient", lambda **kwargs: CountingClient(collection))

    ordering = chroma_utils.get_hierarchy_ordering("acs/acs5", 2023, "county")

    assert ordering == [
        "state",
        "metropolitan statistical area/micropolitan statistical area",
    ]


def test_get_hierarchy_ordering_result_includes_example_url(monkeypatch):
    collection = FakeCollection(_hierarchy_hit_payload())
    monkeypatch.setattr(chroma_utils.chromadb, "PersistentClient", lambda **kwargs: CountingClient(collection))

    result = chroma_utils.get_hierarchy_ordering_result("acs/acs5", 2023, "county")

    assert result.status == "hit"
    assert result.example_url == "for=county:*&in=state:06"
    assert result.geography_hierarchy == "state › county"


def test_planning_tools_share_injected_chroma_client(monkeypatch):
    shared = object()
    monkeypatch.setattr(
        "src.clients.chroma_utils.initialize_chroma_client",
        lambda: shared,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("src.agents.census_query_agent.create_llm", lambda **kwargs: object())
    monkeypatch.setattr(
        "src.agents.census_query_agent.build_agent_backend",
        lambda **kwargs: object(),
    )

    from src.agents.census_query_agent import CensusQueryAgent

    agent = CensusQueryAgent(mode="planning", allow_offline=False)
    by_name = {tool.name: tool for tool in agent.tools}

    assert by_name["resolve_area_name"].chroma_client is shared
    assert by_name["geography_discovery"].chroma_client is shared
    assert by_name["table_catalog_retrieval"].chroma_client is shared


def test_parallel_tool_invocations_reuse_singleton_client(monkeypatch):
    from src.domain.retrieval_plan import RetrievalEvidence

    collection = FakeCollection({"ids": [[]], "metadatas": [[]], "documents": [[]], "distances": [[]]})
    monkeypatch.setattr(chroma_utils.chromadb, "PersistentClient", lambda **kwargs: CountingClient(collection))

    empty_hierarchy = RetrievalEvidence(
        evidence_id="hierarchy-evidence:test",
        collection_name="census_dataset_geographies",
        status="empty",
        query_text="levels",
    )
    empty_area = RetrievalEvidence(
        evidence_id="area-evidence:test",
        collection_name="census_geography_areas",
        status="empty",
        query_text="California",
    )

    def fake_retrieve_geography(*args, **kwargs):
        from src.services.chroma_catalog_retriever import GeographyRetrievalResult

        return GeographyRetrievalResult(hierarchy_evidence=empty_hierarchy, area_evidence=[empty_area])

    monkeypatch.setattr(
        "src.services.chroma_catalog_retriever.retrieve_geography_candidates",
        fake_retrieve_geography,
    )
    monkeypatch.setattr(
        "src.services.chroma_catalog_retriever.retrieve_table_candidates",
        lambda *args, **kwargs: empty_hierarchy,
    )

    shared = chroma_utils.initialize_chroma_client()
    tools = [
        AreaResolutionTool(chroma_client=shared),
        GeographyDiscoveryTool(chroma_client=shared),
        TableCatalogRetrievalTool(chroma_client=shared),
    ]

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(
                lambda tool: tool._run(
                    json.dumps({"name": "California", "geography_type": "state"})
                    if tool.name == "resolve_area_name"
                    else json.dumps({"action": "list_levels"})
                    if tool.name == "geography_discovery"
                    else json.dumps({"query": "population"})
                ),
                tools,
            )
        )

    assert CountingClient.init_count == 1
