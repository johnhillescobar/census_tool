from src.utils.dataset_geography_validator import fetch_dataset_geography_levels, geography_supported


def test_geography_supported_uses_cache(monkeypatch):
    sample_levels = {"state", "county", "place"}

    monkeypatch.setattr(
        "src.utils.dataset_geography_validator._load_disk_cache",
        lambda dataset, year: sample_levels,
    )
    monkeypatch.setattr("src.utils.dataset_geography_validator._CACHE", {})

    result = geography_supported("acs/acs5", 2023, "county")
    assert result["supported"] is True
    assert "county" in result["available_levels"]


def test_fetch_levels_handles_network_error(monkeypatch):
    monkeypatch.setattr("requests.get", lambda url, timeout: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setattr(
        "src.utils.dataset_geography_validator._load_disk_cache",
        lambda dataset, year: {"state"},
    )

    levels = fetch_dataset_geography_levels("acs/acs5", 2023, force_refresh=True)
    assert "state" in levels

