import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

# Load environment variables FIRST
from dotenv import load_dotenv

load_dotenv()

# Import the functions you want to test
from src.llm.category_detector import (
    detect_category_with_llm,
    boost_category_results,
    rerank_by_distance,
)


def test_category_detection():
    """Test LLM category detection"""

    print("=" * 70)
    print("TEST 1: Category Detection")
    print("=" * 70)

    # Test 1: Subject table keywords
    print("\n[Test 1.1] Query: 'demographic overview'")
    result = detect_category_with_llm("demographic overview")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: subject")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "subject", f"Expected 'subject', got '{detected}'"
    print("  ✅ PASS")

    print("\n[Test 1.2] Query: 'give me a summary'")
    result = detect_category_with_llm("give me a summary")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: subject")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "subject", f"Expected 'subject', got '{detected}'"
    print("  ✅ PASS")

    print("\n[Test 1.3] Query: 'general population data'")
    result = detect_category_with_llm("general population data")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: subject")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "subject", f"Expected 'subject', got '{detected}'"
    print("  ✅ PASS")

    # Test 2: Profile table keywords
    print("\n[Test 1.4] Query: 'demographic profile'")
    result = detect_category_with_llm("demographic profile")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: profile")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "profile", f"Expected 'profile', got '{detected}'"
    print("  ✅ PASS")

    print("\n[Test 1.5] Query: 'complete profile of city'")
    result = detect_category_with_llm("complete profile of city")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: profile")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "profile", f"Expected 'profile', got '{detected}'"
    print("  ✅ PASS")

    # Test 3: Comparison keywords
    print("\n[Test 1.6] Query: 'compare income across states'")
    result = detect_category_with_llm("compare income across states")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: cprofile")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "cprofile", f"Expected 'cprofile', got '{detected}'"
    print("  ✅ PASS")

    print("\n[Test 1.7] Query: 'compare income between different counties'")
    result = detect_category_with_llm("compare income between different counties")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: cprofile")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected == "cprofile", f"Expected 'cprofile', got '{detected}'"
    print("  ✅ PASS")

    # Test 4: No preference (accept None or "detail")
    print("\n[Test 1.8] Query: 'total population'")
    result = detect_category_with_llm("total population")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: None or detail")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected in [None, "detail"], f"Expected None or 'detail', got '{detected}'"
    print("  ✅ PASS")

    print("\n[Test 1.9] Query: 'how many people'")
    result = detect_category_with_llm("how many people")
    detected = result.get("preferred_category")
    confidence = result.get("confidence", 0.0)
    print(f"  Expected: None or detail")
    print(f"  Detected: {detected} (confidence: {confidence:.2f})")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    assert detected in [None, "detail"], f"Expected None or 'detail', got '{detected}'"
    print("  ✅ PASS")

    print("\n" + "=" * 70)
    print("✅ All category detection tests passed!")
    print("=" * 70)


def test_distance_boosting():
    """Test distance adjustment"""

    print("\n" + "=" * 70)
    print("TEST 2: Distance Boosting")
    print("=" * 70)

    # Mock ChromaDB results
    results = {
        "ids": [["B05014", "S0101", "B01001"]],
        "distances": [[0.390, 0.394, 0.395]],
        "metadatas": [
            [
                {"table_code": "B05014", "category": "detail"},
                {"table_code": "S0101", "category": "subject"},
                {"table_code": "B01001", "category": "detail"},
            ]
        ],
    }

    print("\nOriginal distances:")
    for id, dist, meta in zip(
        results["ids"][0], results["distances"][0], results["metadatas"][0]
    ):
        print(f"  {id}: {dist:.3f} ({meta['category']})")

    # Boost subject category with confidence 1.0
    boosted = boost_category_results(
        results, "subject", confidence=1.0, boosts_amount=0.05
    )

    print("\nAfter boosting 'subject' category (confidence=1.0, boost=0.05):")
    for id, dist, meta in zip(
        boosted["ids"][0], boosted["distances"][0], boosted["metadatas"][0]
    ):
        print(f"  {id}: {dist:.3f} ({meta['category']})")

    # S0101 should now have distance 0.344 (0.394 - 0.05)
    expected_s0101 = 0.344
    actual_s0101 = boosted["distances"][0][1]

    print(
        f"\nChecking S0101 boost: {actual_s0101:.3f} (expected: {expected_s0101:.3f})"
    )
    assert abs(actual_s0101 - expected_s0101) < 0.001, (
        f"S0101 boost failed: expected {expected_s0101:.3f}, got {actual_s0101:.3f}"
    )
    print("✅ S0101 boosted correctly")

    # Others should be unchanged
    assert boosted["distances"][0][0] == 0.390, "B05014 distance should be unchanged"
    assert boosted["distances"][0][2] == 0.395, "B01001 distance should be unchanged"
    print("✅ Other distances unchanged")

    print("\n" + "=" * 70)
    print("✅ Distance boosting test passed!")
    print("=" * 70)


def test_reranking():
    """Test that results get re-sorted"""

    print("\n" + "=" * 70)
    print("TEST 3: Re-ranking")
    print("=" * 70)

    # After boosting, S0101 should be first
    results = {
        "ids": [["B05014", "S0101", "B01001"]],
        "distances": [[0.390, 0.344, 0.395]],  # S0101 best after boost
        "metadatas": [
            [
                {"table_code": "B05014", "category": "detail"},
                {"table_code": "S0101", "category": "subject"},
                {"table_code": "B01001", "category": "detail"},
            ]
        ],
    }

    print("\nBefore re-ranking:")
    for i, (id, dist) in enumerate(zip(results["ids"][0], results["distances"][0]), 1):
        print(f"  {i}. {id}: {dist:.3f}")

    reranked = rerank_by_distance(results)

    print("\nAfter re-ranking (sorted by distance):")
    for i, (id, dist) in enumerate(
        zip(reranked["ids"][0], reranked["distances"][0]), 1
    ):
        print(f"  {i}. {id}: {dist:.3f}")

    # S0101 should now be first
    print(f"\nChecking rank #1: {reranked['ids'][0][0]} (expected: S0101)")
    assert reranked["ids"][0][0] == "S0101", (
        f"Expected S0101 first, got {reranked['ids'][0][0]}"
    )
    print("✅ S0101 is ranked #1")

    print(f"Checking distance: {reranked['distances'][0][0]:.3f} (expected: 0.344)")
    assert abs(reranked["distances"][0][0] - 0.344) < 0.001, (
        f"Expected distance 0.344, got {reranked['distances'][0][0]:.3f}"
    )
    print("✅ Distance is correct")

    print("\n" + "=" * 70)
    print("✅ Re-ranking test passed!")
    print("=" * 70)


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧪 TESTING CATEGORY DETECTION SYSTEM")
    print("=" * 70)

    try:
        test_category_detection()
        test_distance_boosting()
        test_reranking()

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70 + "\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
