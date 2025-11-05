import csv
import json
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
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)


def run_single_question(
    graph, question: str, question_no: str, user_id: str = "test_user"
):
    """Run a single question through the census graph"""
    try:
        # Create initial state
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

        # Create config
        config = RunnableConfig(
            configurable={"user_id": user_id, "thread_id": f"test_{question_no}"}
        )

        # Process through graph
        result = graph.invoke(initial_state, config)

        # Extract results
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
        logging.error(f"Exception in question {question_no}: {str(e)}", exc_info=True)
        return {
            "success": False,
            "answer": None,
            "generated_files": [],
            "error": str(e),
        }


def test_all_questions():
    """Test all 70 questions from test_questions_new.csv with logging"""

    # Start session logging
    session = SessionLogger("full_test_suite")
    log_file = session.start()

    print("=" * 80)
    print("Census Tool - Full Test Suite")
    print(f"Logging to: {log_file}")
    print("=" * 80)

    # Initialize graph once
    logging.info("Initializing Census graph...")
    try:
        graph = create_census_graph()
        logging.info("Graph initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize graph: {e}", exc_info=True)
        print(f"ERROR: Failed to initialize graph: {e}")
        session.stop()
        return False

    # Read test questions
    test_file = Path("test_questions/test_questions_new.csv")
    if not test_file.exists():
        logging.error(f"Test file not found: {test_file}")
        print(f"ERROR: Test file not found: {test_file}")
        session.stop()
        return False

    with open(test_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        results = []

        for row in reader:
            question_no = row["No"]
            question = row["Question friendly human"]

            # Skip empty rows
            if not question or not question_no:
                continue

            logging.info(f"\n{'=' * 80}")
            logging.info(f"TEST {question_no}: {question}")
            logging.info(f"{'=' * 80}")
            print(f"\nQ{question_no}: {question}")

            # Run the question
            result = run_single_question(graph, question, question_no)

            # Record result
            results.append(
                {
                    "question_no": question_no,
                    "question": question,
                    "status": "PASS"
                    if result["success"]
                    else ("ERROR" if result.get("error") else "FAIL"),
                    "answer": result.get("answer", "No answer"),
                    "generated_files": result.get("generated_files", []),
                    "error": result.get("error"),
                }
            )

            # Log result
            status = results[-1]["status"]
            logging.info(f"Status: {status}")
            if result.get("answer"):
                logging.info(
                    f"Answer: {result['answer'][:200]}..."
                )  # Truncate long answers in log
            if result.get("generated_files"):
                logging.info(f"Files generated: {result['generated_files']}")
            if result.get("error"):
                logging.error(f"Error: {result['error']}")

            # Print progress
            print(f"  -> {status}")

    # Calculate summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total = len(results)

    summary = f"""
{"=" * 80}
TEST RESULTS SUMMARY
{"=" * 80}
Total Questions: {total}
Passed: {passed} ({passed / total * 100:.1f}%)
Failed: {failed} ({failed / total * 100:.1f}%)
Errors: {errors} ({errors / total * 100:.1f}%)
{"=" * 80}
"""

    print(summary)
    logging.info(summary)

    # Save detailed results
    results_file = Path("logs") / "test_sessions" / f"results_{session.timestamp}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logging.info(f"Detailed results saved to: {results_file}")

    # Create summary report
    summary_file = Path("logs") / "test_sessions" / f"summary_{session.timestamp}.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary)
        f.write("\n\nDETAILED RESULTS:\n")
        f.write("=" * 80 + "\n")
        for r in results:
            f.write(f"\nQ{r['question_no']}: {r['question']}\n")
            f.write(f"Status: {r['status']}\n")
            if r["status"] == "PASS":
                f.write(f"Answer: {r['answer'][:200]}...\n")
            if r.get("error"):
                f.write(f"Error: {r['error']}\n")
            f.write("-" * 80 + "\n")

    # Stop session logging
    session.stop()

    print(f"\nComplete logs saved to: {log_file}")
    print(f"Results summary saved to: {results_file}")
    print(f"Human-readable summary: {summary_file}")

    return passed == total


if __name__ == "__main__":
    all_pass = test_all_questions()
    sys.exit(0 if all_pass else 1)
