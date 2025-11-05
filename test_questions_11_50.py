"""
Test runner for questions 11-50 (Complex Geography Queries)
Tests geography patterns including CBSAs, Metropolitan Divisions, NECTAs, Urban Areas, etc.
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
        error = result.get("error")

        success = bool(answer and answer != "No answer" and not error)

        return {
            "success": success,
            "answer": answer,
            "generated_files": generated_files,
            "error": str(error) if error else None,
        }

    except Exception as e:
        logging.error(f"Exception: {str(e)}", exc_info=True)
        return {
            "success": False,
            "answer": None,
            "generated_files": [],
            "error": str(e),
        }


def test_questions_11_to_50():
    """Test questions 11-50 from test_questions_new.csv (Complex Geography)"""

    session = SessionLogger("questions_11_to_50")
    log_file = session.start()

    print("=" * 80)
    print("Testing Questions 11-50 (Complex Geography Queries)")
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

            # Only test questions 11-50
            if question_no < 11:
                continue
            if question_no > 50:
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
            results.append(
                {
                    "question_no": question_no,
                    "question": question,
                    "status": status,
                    "answer": result.get("answer", "")[:150],
                    "files": result.get("generated_files", []),
                    "error": result.get("error"),
                }
            )

            logging.info(f"Status: {status}")
            if result.get("answer"):
                logging.info(f"Answer: {result['answer'][:200]}...")
            if result.get("generated_files"):
                logging.info(f"Files: {result['generated_files']}")
            if result.get("error"):
                logging.error(f"Error: {result['error']}")

            print(f"  -> {status}")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total = len(results)

    summary = f"""
{"=" * 80}
TEST RESULTS: Questions 11-50 (Complex Geography)
{"=" * 80}
Total Questions: {total}
Passed: {passed} ({passed / total * 100:.1f}%)
Failed: {failed} ({failed / total * 100:.1f}%)
Errors: {errors} ({errors / total * 100:.1f}%)
{"=" * 80}
"""

    print(summary)
    logging.info(summary)

    # Detailed breakdown by category
    if failed > 0 or errors > 0:
        print("\nFailed/Error Questions:")
        for r in results:
            if r["status"] != "PASS":
                print(f"  Q{r['question_no']}: {r['status']} - {r['question'][:60]}...")
                if r.get("error"):
                    print(f"    Error: {r['error'][:100]}")

    # Save results
    results_file = (
        Path("logs") / "test_sessions" / f"results_11_50_{session.timestamp}.json"
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
    all_pass = test_questions_11_to_50()
    sys.exit(0 if all_pass else 1)
