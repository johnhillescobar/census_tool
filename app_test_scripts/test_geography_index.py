# app_test_scripts/test_geography_index.py
import json
from index.build_geography_index import build_metadata, upsert_documents
from config import CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME, CHROMA_EMBEDDING_MODEL


class FakeCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, ids, documents, metadatas):
        self.upserts.append((ids, documents, metadatas))


class FakeClient:
    def __init__(self):
        self.called_with = {}

    def get_or_create_collection(self, name, **kwargs):
        self.called_with["name"] = name
        self.called_with["kwargs"] = kwargs
        return FakeCollection()


def test_build_metadata_serializes_ordering_list():
    meta = build_metadata(
        "acs/acs5", 2023, "state › county › tract", "140", ["https://example"]
    )
    assert isinstance(meta["ordering_list"], str)
    assert json.loads(meta["ordering_list"]) == ["state", "county"]


def test_upsert_documents_uses_configured_embedding(monkeypatch):
    fake_client = FakeClient()
    docs = {
        ("acs/acs5", 2023, "state › county"): {
            "category": "detail",
            "dataset": "acs/acs5",
            "year": 2023,
            "hierarchy": "state › county",
            "level_code": "050",
            "examples": ["https://example"],
            "notes": set(),
        }
    }
    upsert_documents(fake_client, docs)
    assert fake_client.called_with["name"] == CHROMA_GEOGRAPHY_HIERARCHY_COLLECTION_NAME
    kwargs = fake_client.called_with["kwargs"]
    emb = kwargs["embedding_function"]
    assert getattr(emb, "model_name", None) == CHROMA_EMBEDDING_MODEL
