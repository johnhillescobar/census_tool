from src.utils.geo_utils import resolve_geography_hint, DEFAULT_GEO


def test_resolve_geography_hint_returns_geo_dict():
    result = resolve_geography_hint("New York City", profile_default_geo=None)
    assert result["level"] == "place"
    assert result["geo_for"] == {"place": "51000"}
    assert result["geo_in"] == {"state": "36"}


def test_resolve_geography_hint_profile_default_augmented():
    profile_geo = {"level": "state", "filters": {"for": "state:48"}, "note": "Texas"}
    result = resolve_geography_hint("", profile_default_geo=profile_geo)
    assert result["geo_for"] == {"state": "48"}
    assert result["geo_in"] == {}


def test_default_geo_contains_geo_dict():
    assert DEFAULT_GEO["geo_for"] == {"place": "51000"}
    assert DEFAULT_GEO["geo_in"] == {"state": "36"}

