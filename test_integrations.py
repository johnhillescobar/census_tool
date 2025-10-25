"""
Test the integrated components:
1. Enumeration detection in geography
2. Category detection in retrieval
3. End-to-end query processing
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.utils.enumeration_detector import detect_and_build_enumeration
from src.llm.category_detector import detect_category_with_llm
from src.services.geography_cache import DynamicGeographyResolver

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_enumeration_detection():
    """Test if enumeration detection works"""
    print("\n" + "=" * 80)
    print("TEST 1: Enumeration Detection")
    print("=" * 80)

    test_queries = [
        ("What's the population of New York City?", False),  # NOT enumeration
        ("Compare population by county in California", True),  # IS enumeration
        ("Show me all counties in Texas", True),  # IS enumeration
        ("List cities in Florida", True),  # IS enumeration
    ]

    for query, should_enumerate in test_queries:
        print(f"\nQuery: {query}")
        result = detect_and_build_enumeration(query)

        if result:
            print(f"  [OK] Enumeration detected: {result['level']}")
            print(f"    Filters: {result['filters']}")
            print(f"    Confidence: {result['confidence']:.2f}")

            if not should_enumerate:
                print(f"  [ERROR] Should NOT enumerate but did!")
        else:
            print(f"  [OK] No enumeration (single location)")
            if should_enumerate:
                print(f"  [ERROR] Should enumerate but didn't!")

    print("\n[SUCCESS] Enumeration detection tests complete")


def test_category_detection():
    """Test if category detection works"""
    print("\n" + "=" * 80)
    print("TEST 2: Category Detection")
    print("=" * 80)

    test_queries = [
        "What's the population of New York City?",
        "Show me median income trends from 2015 to 2020",
        "Give me a demographic overview of California",
        "Show me a full demographic profile of Texas",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = detect_category_with_llm(query)
            preferred = result.get("preferred_category")
            confidence = result.get("confidence", 0.0)
            reasoning = result.get("reasoning", "No reasoning provided")

            print(f"  [OK] Category: {preferred or 'none'}")
            print(f"    Confidence: {confidence:.2f}")
            print(f"    Reasoning: {reasoning[:100]}...")
        except Exception as e:
            print(f"  [ERROR] {str(e)}")

    print("\n[SUCCESS] Category detection tests complete")


def test_geography_with_enumeration():
    """Test if geography resolver handles enumeration"""
    print("\n" + "=" * 80)
    print("TEST 3: Geography Resolution with Enumeration")
    print("=" * 80)

    resolver = DynamicGeographyResolver()

    test_queries = [
        "New York City",
        "Compare population by county in California",
        "All counties in Texas",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = resolver.resolve_geography_from_text(query)
            print(f"  [OK] Level: {result.level}")
            print(f"    Filters: {result.filters}")
            print(f"    Confidence: {result.confidence:.2f}")
            print(f"    Note: {result.note}")

            # Check if enumeration worked
            if "county" in query.lower() and "in" in query.lower():
                if result.filters.get("for", "").endswith(":*"):
                    print(f"  [SUCCESS] Enumeration correctly detected!")
                else:
                    print(f"  [ERROR] Should have enumeration but got single area")
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            import traceback

            traceback.print_exc()

    print("\n[SUCCESS] Geography resolution tests complete")


def main():
    """Run all integration tests"""
    print("\n" + "=" * 80)
    print("INTEGRATION TESTS - Phase 9 Component Connections")
    print("=" * 80)

    try:
        test_enumeration_detection()
        test_category_detection()
        test_geography_with_enumeration()

        print("\n" + "=" * 80)
        print("[SUCCESS] ALL INTEGRATION TESTS COMPLETE")
        print("=" * 80)
        print("\nNext step: Run the main app with:")
        print("  python main.py")
        print("\nTry these queries:")
        print("  1. What's the population of New York City?")
        print("  2. Show me median income trends from 2015 to 2020")
        print("  3. Compare population by county in California")

    except Exception as e:
        print(f"\n[ERROR] TEST SUITE FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
