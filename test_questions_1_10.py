"""
Test runner for questions 1-10 only
Quick validation that basic functionality works before running full suite
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
        error = result.get("error")

        success = bool(answer and answer != "No answer" and not error)

        return {
            "success": success,
            "answer": answer,
            "error": str(error) if error else None,
        }

    except Exception as e:
        logging.error(f"Exception: {str(e)}", exc_info=True)
        return {"success": False, "answer": None, "error": str(e)}


def test_questions_1_to_10():
    """Test questions 1-10 from test_questions_new.csv"""

    session = SessionLogger("questions_1_to_10")
    log_file = session.start()

    print("Testing Questions 1-10")
    print(f"Logging to: {log_file}")
    print("=" * 60)

    # Initialize graph
    logging.info("Initializing Census graph...")
    graph = create_census_graph()

    # Read test questions
    test_file = Path("test_questions/test_questions_new.csv")
    with open(test_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        results = []

        for row in reader:
            question_no = int(row["No"])
            if question_no > 10:
                break

            question = row["Question friendly human"]

            logging.info(f"\nTEST {question_no}: {question}")
            print(f"\nQ{question_no}: {question[:60]}...")

            result = run_single_question(graph, question, str(question_no))

            status = "PASS" if result["success"] else "FAIL"
            results.append(
                {
                    "question_no": question_no,
                    "status": status,
                    "answer": result.get("answer", "")[:100],
                }
            )

            logging.info(f"Status: {status}")
            print(f"  -> {status}")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed}/{total} passed")
    print(f"{'=' * 60}")

    logging.info(f"\nRESULTS: {passed}/{total} passed")

    session.stop()

    return passed == total


if __name__ == "__main__":
    all_pass = test_questions_1_to_10()
    sys.exit(0 if all_pass else 1)
