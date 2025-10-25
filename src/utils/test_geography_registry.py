"""
Test the Geography Registry
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.geography_registry import GeographyRegistry


def test_enumerate_counties():
    """Test enumerating California counties"""
    print("=" * 70)
    print("TEST 1: Enumerate California Counties")
    print("=" * 70)

    registry = GeographyRegistry()

    # Enumerate all counties in California
    counties = registry.enumerate_areas(
        dataset="acs/acs5", year=2023, geo_token="county", parent_geo={"state": "06"}
    )

    print(f"\nFound {len(counties)} counties in California")
    print("\nFirst 5 counties:")
    for i, (name, metadata) in enumerate(list(counties.items())[:5], 1):
        print(f"  {i}. {name} (code: {metadata['code']})")

    assert len(counties) == 58, (
        f"California should have 58 counties, found {len(counties)}"
    )
    print("\n✅ Test passed!")

    return counties


def test_find_county_code():
    """Test finding a specific county code"""
    print("\n" + "=" * 70)
    print("TEST 2: Find Los Angeles County Code")
    print("=" * 70)

    registry = GeographyRegistry()

    # Find Los Angeles County
    result = registry.find_area_code(
        friendly_name="Los Angeles",
        geo_token="county",
        dataset="acs/acs5",
        year=2023,
        parent_geo={"state": "06"},
    )

    if result:
        print(f"\n✅ Found: {result['full_name']}")
        print(f"   Code: {result['code']}")
        print(f"   GEO_ID: {result['geo_id']}")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Match type: {result['match_type']}")

        assert result["code"] == "037", (
            f"LA County code should be 037, got {result['code']}"
        )
        print("\n✅ Test passed!")
    else:
        print("❌ Not found!")
        assert False, "Should have found Los Angeles County"

    return result


def test_enumerate_states():
    """Test enumerating all US states"""
    print("\n" + "=" * 70)
    print("TEST 3: Enumerate All US States")
    print("=" * 70)

    registry = GeographyRegistry()

    states = registry.enumerate_areas(dataset="acs/acs5", year=2023, geo_token="state")

    print(f"\nFound {len(states)} states/territories")
    print("\nFirst 10:")
    for i, (name, metadata) in enumerate(list(states.items())[:10], 1):
        print(f"  {i}. {name} (code: {metadata['code']})")

    # US has 50 states + DC + PR + territories ≈ 52-54
    assert len(states) >= 50, f"Should have at least 50 states, found {len(states)}"
    print("\n✅ Test passed!")

    return states


if __name__ == "__main__":
    print("\n🧪 TESTING GEOGRAPHY REGISTRY\n")

    try:
        counties = test_enumerate_counties()
        la_county = test_find_county_code()
        states = test_enumerate_states()

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\nCached data:")
        print(f"  • {len(counties)} California counties")
        print(f"  • {len(states)} US states")
        print("\n✅ Geography Registry is working!\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        raise
