from typing import Dict, Any

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def display_results(result: Dict[str, Any]):
    """Display the results of the Census query"""

    print("\n" + "=" * 50)
    print("📊 CENSUS DATA RESULTS")
    print("=" * 50)

    # Check for errors
    if result.get("error"):
        print(f"\n❌ Error: {result['error']}")
        return

    # Display final answer
    final = result.get("final")
    if not final:
        print("\n❌ No answer available")
        return

    # Display answer type
    answer_type = final.get("type", "Unknown")
    print(f"\n📊 Answer Type: {answer_type}")

    if answer_type == "single":
        display_single_value(final)
    elif answer_type == "series":
        display_series(final)
    elif answer_type == "table":
        display_table(final)
    elif answer_type == "not_census":
        display_not_census(final)
    else:
        print(f"�� Answer: {final}")

    # Display footnotes
    footnotes = final.get("footnotes", [])
    if footnotes:
        print("\n📝 Footnotes:")
        logger.info(f"Footnotes: {footnotes}")
        for i, footnote in enumerate(footnotes):
            print(f"  {i + 1}. {footnote}")

    # Display logs if any
    logs = result.get("logs", [])
    if logs:
        print(f"\n�� System Logs: {len(logs)} entries")
        logger.info(f"System Logs: {logs}")
        for log in logs[-3:]:  # Show last 3 logs
            print(f"  • {log}")


def display_single_value(final: Dict[str, Any]):
    """Display a single value answer"""

    value = final.get("value", "N/A")
    geo = final.get("geo", "Unknown location")
    year = final.get("year", "Unknown year")
    variable = final.get("variable", "Unknown variable")

    print(f"�� Location: {geo}")
    print(f"📅 Year: {year}")
    print(f"📊 Value: {value}")
    if variable != "Unknown variable":
        print(f"�� Variable: {variable}")


def display_series(final: Dict[str, Any]):
    """Display a time series answer"""

    data = final.get("data", [])
    geo = final.get("geo", "Unknown location")
    variable = final.get("variable", "Unknown variable")

    print(f"📍 Location: {geo}")
    print(f"🔢 Variable: {variable}")
    print(f"📈 Time Series Data:")

    if not data:
        print("  No data available")
        return

    # Display first 10 years
    for item in data[:10]:
        year = item.get("year", "Unknown")
        value = item.get("formatted_value", item.get("value", "N/A"))
        print(f"  {year}: {value}")

    if len(data) > 10:
        print(f"  ... and {len(data) - 10} more years")

    # Show file path if available
    file_path = final.get("file_path")
    if file_path:
        print(f"\n�� Full data saved to: {file_path}")


def display_table(final: Dict[str, Any]):
    """Display a table answer"""

    data = final.get("data", [])
    total_rows = final.get("total_rows", 0)
    columns = final.get("columns", [])

    print(f"📊 Table Data ({total_rows} rows):")

    if not data:
        print("  No data available")
        return

    # Display column headers
    if columns:
        print("  " + " | ".join(columns[:5]))  # First 5 columns
        print("  " + "-" * (len(" | ".join(columns[:5]))))

    # Display first 10 rows
    for i, row in enumerate(data[:10]):
        if isinstance(row, dict):
            values = [str(row.get(col, "")) for col in columns[:5]]
            print("  " + " | ".join(values))
        else:
            print(f"  Row {i + 1}: {row}")

    if len(data) > 10:
        print(f"  ... and {len(data) - 10} more rows")

    # Show file path if available
    file_path = final.get("file_path")
    if file_path:
        print(f"\n💾 Full data saved to: {file_path}")


def display_not_census(final: Dict[str, Any]):
    """Display a non-Census response"""

    message = final.get("message", "I can't help with that.")
    suggestion = final.get("suggestion", "")

    print(f"ℹ️  {message}")
    if suggestion:
        print(f"�� {suggestion}")
