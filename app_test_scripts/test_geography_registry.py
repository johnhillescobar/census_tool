from src.utils.geography_registry import GeographyRegistry


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

    monkeypatch.setattr("src.utils.geography_registry.record_event", fake_record_event)

    def fake_validate(dataset, year, geo_for, geo_in, *args, **kwargs):
        return (
            next(iter(geo_for.keys())),
            next(iter(geo_for.values())),
            [
                ("metropolitan statistical area/micropolitan statistical area", "35620"),
                ("metropolitan division", "35614"),
                ("state (or part)", "36"),
            ],
        )

    monkeypatch.setattr(
        "src.utils.geography_registry.validate_and_fix_geo_params", fake_validate
    )

    captured["url"] = None

    def fake_get(url, timeout):
        captured["url"] = url
        rows = [
            ["NAME", "GEO_ID", "county"],
            ["Example County, Sample", "0500000US12345", "12345"],
        ]
        return FakeResponse(url, rows)

    monkeypatch.setattr("requests.get", fake_get)

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

