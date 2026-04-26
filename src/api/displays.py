from typing import Dict, Any

from src.state.types import FinalResponseState

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _coerce_final_response_state(value: Any) -> FinalResponseState | None:
    try:
        if isinstance(value, FinalResponseState):
            return value
        elif isinstance(value, dict):
            return FinalResponseState.model_validate(value)
    except Exception as exc:
        logger.warning("Skipping invalid final response state: %s", exc)
        return None


def display_results(result: Dict[str, Any]) -> None:
    """Display the results of the Census query"""

    print("\n" + "=" * 50)
    print("CENSUS DATA RESULTS")
    print("=" * 50)

    # Check for errors
    if result.get("error"):
        print(f"\n[ERROR] Error: {result['error']}")
        return

    # Display final answer
    final = _coerce_final_response_state(result.get("final"))
    if not final:
        print("\n[ERROR] No answer available")
        return

    # Phase 3 format: Display answer_text from agent
    if final.answer_text:
        print(f"\n[ANSWER] {final.answer_text}")

    # Phase 3: Display generated files
    generated_files = final.generated_files if final.generated_files else []
    if generated_files:
        print(f"\n[FILES GENERATED]: {len(generated_files)} file(s)")
        for i, file_info in enumerate(generated_files, 1):
            print(f"  {i}. {file_info}")

    if final.charts_needed:
        print(f"\n[CHARTS REQUESTED]: {len(final.charts_needed)} chart(s)")
        for chart in final.charts_needed:
            print(f"  - {chart.type.title()} chart: {chart.title or 'Untitled'}")

    if final.tables_needed:
        print(f"\n[TABLES REQUESTED]: {len(final.tables_needed)} table(s)")
        for table in final.tables_needed:
            print(f"  - {table.format.upper()} table: {table.filename or 'untitled'}")

    # Display footnotes
    if final.footnotes:
        print("\n📝 Footnotes:")
        logger.info(f"Footnotes: {final.footnotes}")
        for i, footnote in enumerate(final.footnotes):
            print(f"  {i + 1}. {footnote}")

    # Display logs if any
    logs = result.get("logs", [])
    if logs:
        print(f"\n�� System Logs: {len(logs)} entries")
        logger.info(f"System Logs: {logs}")
        for log in logs[-3:]:  # Show last 3 logs
            print(f"  • {log}")



