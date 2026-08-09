import json

from src.clients import chroma_utils
from src.clients.chroma_utils import HierarchyLookupResult


def test_get_hierarchy_ordering_returns_normalized_order(monkeypatch):
    chroma_utils.reset_chroma_client()
    monkeypatch.setattr(
        chroma_utils,
        "get_hierarchy_ordering_result",
        lambda dataset, year, for_level: HierarchyLookupResult(
            status="hit",
            dataset=dataset,
            year=year,
            for_level=for_level,
            ordering=[
                "state",
                "metropolitan statistical area/micropolitan statistical area",
            ],
            hierarchy_id="hierarchy:1",
        ),
    )

    ordering = chroma_utils.get_hierarchy_ordering("acs/acs5", 2023, "county")

    assert ordering == [
        "state",
        "metropolitan statistical area/micropolitan statistical area",
    ]


def test_get_hierarchy_ordering_handles_missing_metadata(monkeypatch):
    chroma_utils.reset_chroma_client()
    monkeypatch.setattr(
        chroma_utils,
        "get_hierarchy_ordering_result",
        lambda dataset, year, for_level: HierarchyLookupResult(
            status="empty",
            dataset=dataset,
            year=year,
            for_level=for_level,
        ),
    )

    ordering = chroma_utils.get_hierarchy_ordering("acs/acs5", 2023, "county")

    assert ordering == []


def test_validate_and_fix_geo_params_orders_and_normalizes(monkeypatch):
    chroma_utils.reset_chroma_client()
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
