from src.domain.geography_registry import GeographyRegistry


class FakeResponse:
    def __init__(self, url, rows):
        self._url = url
        self._rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return self._rows


def test_enumerate_areas_orders_parents(monkeypatch, tmp_path):
    captured = {}

    def fake_record_event(event_type, payload):
        if event_type == "enumerate_areas":
            captured["payload"] = payload

    monkeypatch.setattr("src.domain.geography_registry.record_event", fake_record_event)

    def fake_validate(dataset, year, geo_for, geo_in, *args, **kwargs):
        return (
            next(iter(geo_for.keys())),
            next(iter(geo_for.values())),
            [
                (
                    "metropolitan statistical area/micropolitan statistical area",
                    "35620",
                ),
                ("metropolitan division", "35614"),
                ("state (or part)", "36"),
            ],
        )

    monkeypatch.setattr(
        "src.domain.geography_registry.validate_and_fix_geo_params", fake_validate
    )

    captured["url"] = None

    def fake_fetch(url, *, timeout=30):
        captured["url"] = url
        return [
            ["NAME", "GEO_ID", "county"],
            ["Example County, Sample", "0500000US12345", "12345"],
        ]

    monkeypatch.setattr("src.domain.geography_registry._fetch_census_json", fake_fetch)

    registry = GeographyRegistry(cache_dir=str(tmp_path))
    parent_geo = {
        "metropolitan division": "35614",
        "state (or part)": "36",
        "metropolitan statistical area/micropolitan statistical area": "35620",
    }

    areas = registry.enumerate_areas(
        "acs/acs5", 2023, "county", parent_geo=parent_geo, force_refresh=True
    )

    assert "Example County, Sample" in areas
    assert captured["payload"]["area_count"] == 1
    assert "for=county:*" in captured["url"]
    assert (
        "metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620"
        in captured["url"]
    )
    assert captured["payload"]["parent_levels"][0][0] == (
        "metropolitan statistical area/micropolitan statistical area"
    )


def test_find_area_code_resolves_state_without_enumeration(monkeypatch, tmp_path):
    registry = GeographyRegistry(cache_dir=str(tmp_path))

    def fail_enumerate(*args, **kwargs):
        raise AssertionError("enumerate_areas should not be called for state lookup")

    monkeypatch.setattr(registry, "enumerate_areas", fail_enumerate)

    result = registry.find_area_code(
        "California", "state", "acs/acs5", 2023, parent_geo=None
    )

    assert result is not None
    assert result["code"] == "06"
    assert result["match_type"] == "Exact match"


def test_append_census_api_key_adds_key_query_param(monkeypatch):
    from src.domain.geography_registry import _append_census_api_key

    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    url = _append_census_api_key(
        "https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=state:*"
    )
    assert url.endswith("key=test-key")


def test_enumerate_areas_appends_census_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CENSUS_API_KEY", "test-key")

    captured = {}

    def fake_fetch(url, *, timeout=30):
        from src.domain.geography_registry import _append_census_api_key

        captured["url"] = _append_census_api_key(url)
        return [
            ["NAME", "GEO_ID", "state"],
            ["California", "0400000US06", "06"],
        ]

    monkeypatch.setattr("src.domain.geography_registry._fetch_census_json", fake_fetch)
    monkeypatch.setattr(
        "src.domain.geography_registry.validate_and_fix_geo_params",
        lambda dataset, year, geo_for, geo_in, *args, **kwargs: (
            next(iter(geo_for.keys())),
            next(iter(geo_for.values())),
            [],
        ),
    )

    registry = GeographyRegistry(cache_dir=str(tmp_path))
    areas = registry.enumerate_areas(
        "acs/acs5", 2023, "state", parent_geo=None, force_refresh=True
    )

    assert "California" in areas
    assert "key=test-key" in captured["url"]
