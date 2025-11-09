import json

import pytest

from src.utils import chroma_utils


class DummyCollection:
    def __init__(self, payload):
        self._payload = payload

    def get(self, **kwargs):
        return self._payload


class DummyClient:
    def __init__(self, payload):
        self._payload = payload

    def get_collection(self, name):
        return DummyCollection(self._payload)


def test_get_hierarchy_ordering_returns_normalized_order(monkeypatch):
    chroma_utils.get_hierarchy_ordering.cache_clear()
    payload = {
        "metadatas": [
            {"ordering_list": json.dumps(["state", "cbsa"])},
        ]
    }
    monkeypatch.setattr(
        chroma_utils, "initialize_chroma_client", lambda: DummyClient(payload)
    )

    ordering = chroma_utils.get_hierarchy_ordering("acs/acs5", 2023, "county")

    expected = [
        "state",
        "metropolitan statistical area/micropolitan statistical area",
    ]
    assert ordering == expected


def test_get_hierarchy_ordering_handles_missing_metadata(monkeypatch):
    chroma_utils.get_hierarchy_ordering.cache_clear()
    payload = {"metadatas": []}
    monkeypatch.setattr(
        chroma_utils, "initialize_chroma_client", lambda: DummyClient(payload)
    )

    ordering = chroma_utils.get_hierarchy_ordering("acs/acs5", 2023, "county")

    assert ordering == []


def test_validate_and_fix_geo_params_orders_and_normalizes(monkeypatch):
    chroma_utils.get_hierarchy_ordering.cache_clear()
    monkeypatch.setattr(
        chroma_utils,
        "get_hierarchy_ordering",
        lambda dataset, year, for_level: [
            "state",
            "metropolitan statistical area/micropolitan statistical area",
        ],
    )

    for_token, for_value, ordered_in = chroma_utils.validate_and_fix_geo_params(
        dataset="acs/acs5",
        year=2023,
        geo_for={"state": "06", "county": "037"},
        geo_in={"cbsa": "35620"},
    )

    assert for_token == "county"
    assert for_value == "037"
    assert ordered_in == [
        ("state", "06"),
        ("metropolitan statistical area/micropolitan statistical area", "35620"),
    ]

