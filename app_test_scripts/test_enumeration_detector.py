from src.utils.enumeration_detector import EnumerationDetector


def test_build_enumeration_filters_returns_geo_dicts():
    detector = EnumerationDetector()
    request = detector.detect("List all counties in California")
    assert request.needs_enumeration is True

    data = detector.build_enumeration_filters(request)
    assert data["filters"]["for"] == "county:*"
    assert data["geo_for"] == {"county": "*"}
    assert data["geo_in"] == {"state": "06"}
