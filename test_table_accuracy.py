"""
Test Table Selection Accuracy for Phase 8

This script tests how accurately the table-level retrieval system
finds the correct Census tables for common natural language queries.

Target: 85%+ accuracy before moving to Phase 9
"""

import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from src.utils.retrieval_utils_tables import search_tables_chroma
from config import CHROMA_PERSIST_DIRECTORY

load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


logger = logging.getLogger(__name__)

load_dotenv()


def test_table_accuracy():
    """Test table selection accuracy with known queries"""

    # Test cases: (query, expected_table, category)
    test_cases = [
        # Basic population queries
        ("NYC population", "B01003", "population"),
        ("total population", "B01003", "population"),
        ("how many people live in", "B01003", "population"),
        ("population count", "B01003", "population"),
        # Income queries
        ("median household income", "B19013", "income"),
        ("median income", "B19013", "income"),
        ("household income", "B19013", "income"),
        ("how much do people earn", "B19013", "income"),
        # Housing queries
        ("homeownership rate", "B25003", "housing"),
        ("owner occupied housing", "B25003", "housing"),
        ("renters vs owners", "B25003", "housing"),
        # Other common queries
        ("poverty status", "B17001", "poverty"),
        ("total housing units", "B25001", "housing"),
        ("median age", "B01002", "demographics"),
        ("educational attainment", "B15003", "education"),
        ("race demographics", "B02001", "race"),
    ]

    print("=" * 80)
    print("PHASE 8: TABLE SELECTION ACCURACY TEST")
    print("=" * 80)
    print()

    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIRECTORY))
    collection = client.get_collection("census_tables")

    correct = 0
    total = len(test_cases)
    failures = []

    for query, expected_table, category in test_cases:
        print(f"Query: '{query}'")
        print(f"Expected: {expected_table} ({category})")

        # Search for tables
        try:
            results = search_tables_chroma(
                collection=collection, query=query, k=5, dataset_filter="acs/acs5"
            )

            if results:
                top_result = results[0]
                found_table = top_result.get("table_code", "UNKNOWN")
                confidence = top_result.get("score", 0.0)
                distance = top_result.get("distance", 999)

                # Check if correct
                is_correct = found_table == expected_table
                status = "✅ CORRECT" if is_correct else "❌ WRONG"

                print(
                    f"Found: {found_table} (confidence: {confidence:.2f}, distance: {distance:.3f}) {status}"
                )

                if is_correct:
                    correct += 1
                else:
                    # Show top 5 results for debugging
                    print("  Top 5 results:")
                    for i, result in enumerate(results[:5], 1):
                        table_code = result.get("table_code", "UNKNOWN")
                        conf = result.get("confidence_score", 0.0)
                        dist = result.get("distance", 999)
                        marker = "👈 Expected" if table_code == expected_table else ""
                        print(
                            f"    {i}. {table_code} (conf: {conf:.2f}, dist: {dist:.3f}) {marker}"
                        )

                    failures.append(
                        {
                            "query": query,
                            "expected": expected_table,
                            "found": found_table,
                            "category": category,
                            "top_5": [r.get("table_code") for r in results[:5]],
                        }
                    )
            else:
                print("❌ NO RESULTS")
                failures.append(
                    {
                        "query": query,
                        "expected": expected_table,
                        "found": "NO RESULTS",
                        "category": category,
                        "top_5": [],
                    }
                )

        except Exception as e:
            print(f"❌ ERROR: {e}")
            failures.append(
                {
                    "query": query,
                    "expected": expected_table,
                    "found": f"ERROR: {e}",
                    "category": category,
                    "top_5": [],
                }
            )

        print()

    # Summary
    accuracy = (correct / total) * 100
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Correct: {correct}/{total}")
    print(f"Accuracy: {accuracy:.1f}%")
    print()

    if accuracy >= 85:
        print("🎉 EXCELLENT! Ready for Phase 9!")
    elif accuracy >= 67:
        print("⚠️  GOOD PROGRESS - Need tuning to reach 85%")
    else:
        print("❌ NEEDS WORK - Below baseline")

    print()

    # Failure analysis
    if failures:
        print("=" * 80)
        print("FAILURES TO ANALYZE")
        print("=" * 80)

        # Group by category
        by_category = {}
        for failure in failures:
            cat = failure["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(failure)

        for category, fails in by_category.items():
            print(f"\n{category.upper()} ({len(fails)} failures):")
            for fail in fails:
                print(f"  • '{fail['query']}'")
                print(f"    Expected: {fail['expected']}, Found: {fail['found']}")
                if fail["top_5"]:
                    in_top_5 = fail["expected"] in fail["top_5"]
                    if in_top_5:
                        rank = fail["top_5"].index(fail["expected"]) + 1
                        print(
                            f"    ⚠️  Expected table IS in top 5 (rank #{rank}) - scoring issue"
                        )
                    else:
                        print("    ❌ Expected table NOT in top 5 - retrieval issue")

    return accuracy, failures


def analyze_specific_query(query, expected_table, n_results=10):
    """Deep dive into why a specific query fails"""

    print("=" * 80)
    print(f"DEEP ANALYSIS: '{query}'")
    print(f"Expected: {expected_table}")
    print("=" * 80)
    print()

    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIRECTORY))
    collection = client.get_collection("census_tables")

    # Query ChromaDB directly to see raw results
    results = collection.query(query_texts=[query], n_results=n_results)

    print(f"Top {n_results} results from ChromaDB:")
    print()

    for i in range(len(results["ids"][0])):
        table_code = results["ids"][0][i]
        distance = results["distances"][0][i]
        metadata = results["metadatas"][0][i]

        is_expected = "👈 EXPECTED" if table_code == expected_table else ""

        print(f"{i + 1}. {table_code} (distance: {distance:.3f}) {is_expected}")
        print(f"   Description: {metadata.get('description', 'N/A')[:100]}...")
        print()

    # Check if expected table is in results at all
    if expected_table in results["ids"][0]:
        rank = results["ids"][0].index(expected_table) + 1
        print(f"✅ Expected table found at rank #{rank}")
        print(f"   This is a SCORING issue - need to boost {expected_table}")
    else:
        print(f"❌ Expected table NOT in top {n_results}")
        print(f"   This is a RETRIEVAL issue - ChromaDB isn't finding {expected_table}")
        print("   May need to improve table descriptions in index")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test Phase 8 table selection accuracy"
    )
    parser.add_argument("--analyze", type=str, help="Deep dive into a specific query")
    parser.add_argument(
        "--expected", type=str, help="Expected table for --analyze query"
    )

    args = parser.parse_args()

    if args.analyze and args.expected:
        # Deep analysis mode
        analyze_specific_query(args.analyze, args.expected)
    else:
        # Full accuracy test
        accuracy, failures = test_table_accuracy()

        print()
        print("=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print()

        if accuracy < 85:
            print("To improve accuracy:")
            print("1. Run deep analysis on failures:")
            print(
                '   python test_table_accuracy.py --analyze "median household income" --expected B19013'
            )
            print()
            print("2. Check if expected tables are in results:")
            print(
                "   - If YES: Scoring issue → adjust calculate_table_confidence_score()"
            )
            print(
                "   - If NO: Retrieval issue → improve table descriptions in build_index_tables.py"
            )
            print()
            print("3. Common fixes:")
            print("   - Increase table_name_boost in retrieval_utils_tables.py")
            print("   - Add IMPORTANT_TABLES dict with boosted tables")
            print("   - Enhance table descriptions with more keywords")
