"""
Test runner for questions 51-70 (Multi-Year Time Series Queries)
Tests the new multi-year support where agent makes multiple API calls per year range
"""

import csv
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

from app import create_census_graph
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig
from src.utils.session_logger import SessionLogger

# Load environment variables
load_dotenv()

# Set up basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def run_single_question(graph, question: str, question_no: str):
    """Run a single question through the census graph"""
    try:
        initial_state = CensusState(
            messages=[{"role": "user", "content": question}],
            original_query=None,
            intent=None,
            geo={},
            candidates={},
            plan=None,
            artifacts={},
            final=None,
            logs=[],
            error=None,
            summary=None,
            profile={},
            history=[],
            cache_index={},
        )

        config = RunnableConfig(
            configurable={"user_id": "test_user", "thread_id": f"test_{question_no}"}
        )

        result = graph.invoke(initial_state, config)

        final = result.get("final", {})
        answer = final.get("answer_text", "No answer")
        generated_files = final.get("generated_files", [])
        charts_needed = final.get("charts_needed", [])
        error = result.get("error")

        # For multi-year queries, verify line chart is generated
        has_line_chart = any(c.get("type") == "line" for c in charts_needed)

        success = bool(answer and answer != "No answer" and not error)

        return {
            "success": success,
            "answer": answer,
            "generated_files": generated_files,
            "charts_needed": charts_needed,
            "has_line_chart": has_line_chart,
            "error": str(error) if error else None,
        }

    except Exception as e:
        logging.error(f"Exception: {str(e)}", exc_info=True)
        return {
            "success": False,
            "answer": None,
            "generated_files": [],
            "charts_needed": [],
            "has_line_chart": False,
            "error": str(e),
        }


def test_questions_51_to_70():
    """Test questions 51-70 from test_questions_new.csv (Multi-Year Time Series)"""

    session = SessionLogger("questions_51_to_70")
    log_file = session.start()

    print("=" * 80)
    print("Testing Questions 51-70 (Multi-Year Time Series Queries)")
    print("These test the new multi-year support added in Phase 2")
    print(f"Logging to: {log_file}")
    print("=" * 80)

    # Initialize graph
    logging.info("Initializing Census graph...")
    graph = create_census_graph()
    logging.info("Graph initialized successfully")

    # Read test questions
    test_file = Path("test_questions/test_questions_new.csv")
    with open(test_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        results = []

        for row in reader:
            question_no = int(row["No"])

            # Only test questions 51-70
            if question_no < 51:
                continue
            if question_no > 70:
                break

            question = row["Question friendly human"]

            logging.info(f"\n{'=' * 80}")
            logging.info(f"TEST {question_no}: {question}")
            logging.info(f"{'=' * 80}")
            print(f"\nQ{question_no}: {question[:70]}...")

            result = run_single_question(graph, question, str(question_no))

            status = (
                "PASS"
                if result["success"]
                else ("ERROR" if result.get("error") else "FAIL")
            )

            # Additional validation for multi-year queries
            if result["success"] and not result["has_line_chart"]:
                logging.warning(
                    f"Q{question_no}: SUCCESS but no line chart generated (expected for time series)"
                )

            results.append(
                {
                    "question_no": question_no,
                    "question": question,
                    "status": status,
                    "answer": result.get("answer", "")[:150],
                    "files": result.get("generated_files", []),
                    "charts_needed": result.get("charts_needed", []),
                    "has_line_chart": result.get("has_line_chart", False),
                    "error": result.get("error"),
                }
            )

            logging.info(f"Status: {status}")
            if result.get("answer"):
                logging.info(f"Answer: {result['answer'][:200]}...")
            if result.get("charts_needed"):
                logging.info(f"Charts: {result['charts_needed']}")
            if result.get("has_line_chart"):
                logging.info("Line chart: YES (correct for time series)")
            if result.get("generated_files"):
                logging.info(f"Files: {result['generated_files']}")
            if result.get("error"):
                logging.error(f"Error: {result['error']}")

            print(
                f"  -> {status}{' (line chart)' if result.get('has_line_chart') else ''}"
            )

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    with_line_charts = sum(1 for r in results if r.get("has_line_chart"))
    total = len(results)

    summary = f"""
{"=" * 80}
TEST RESULTS: Questions 51-70 (Multi-Year Time Series)
{"=" * 80}
Total Questions: {total}
Passed: {passed} ({passed / total * 100:.1f}%)
Failed: {failed} ({failed / total * 100:.1f}%)
Errors: {errors} ({errors / total * 100:.1f}%)
With Line Charts: {with_line_charts} ({with_line_charts / total * 100:.1f}%)
{"=" * 80}
MULTI-YEAR SUPPORT: {"WORKING" if passed > total * 0.8 else "NEEDS REVIEW"}
{"=" * 80}
"""

    print(summary)
    logging.info(summary)

    # Detailed breakdown
    if failed > 0 or errors > 0:
        print("\nFailed/Error Questions:")
        for r in results:
            if r["status"] != "PASS":
                print(f"  Q{r['question_no']}: {r['status']} - {r['question'][:60]}...")
                if r.get("error"):
                    print(f"    Error: {r['error'][:100]}")

    # Check line chart usage
    if with_line_charts < total * 0.8:
        print(
            f"\nWARNING: Only {with_line_charts}/{total} queries generated line charts"
        )
        print("Expected: Most time series queries should use line charts")

    # Save results
    results_file = (
        Path("logs") / "test_sessions" / f"results_51_70_{session.timestamp}.json"
    )
    import json

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logging.info(f"Results saved to: {results_file}")

    session.stop()

    print(f"\nComplete logs saved to: {log_file}")
    print(f"Results saved to: {results_file}")

    return passed == total


if __name__ == "__main__":
    all_pass = test_questions_51_to_70()
    sys.exit(0 if all_pass else 1)



