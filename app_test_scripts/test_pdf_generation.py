"""
Test PDF generation functionality.
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.clients import generate_session_pdf


def _sample_census_data() -> dict:
    return {
        "success": True,
        "request": {
            "year": 2023,
            "dataset": "acs/acs5",
            "variables": ["B01003_001E"],
            "geo_for": {"place": "44000"},
            "geo_in": {"state": "06"},
            "geo_in_chained": [],
        },
        "headers": ["NAME", "B01003_001E"],
        "records": [
            {
                "values": {
                    "NAME": "Los Angeles",
                    "B01003_001E": "9848406",
                }
            }
        ],
        "row_count": 1,
        "error": None,
        "error_message": None,
    }


def _sample_entry(*, generated_files: list[dict], census_data: dict) -> dict:
    return {
        "question": "What's the population of Los Angeles?",
        "timestamp": datetime.now(),
        "result": {
            "final": {
                "answer_text": (
                    "Los Angeles has a population of 9.8 million people "
                    "according to the 2020 Census."
                ),
                "generated_files": generated_files,
                "footnotes": [],
                "charts_needed": [],
                "tables_needed": [],
            },
            "artifacts": {
                "census_data": census_data,
                "variable_labels": {"labels": {"B01003_001E": "Total Population"}},
                "data_summary": "Population table for Los Angeles.",
                "reasoning_trace": "Used typed census response fixture.",
                "comparison_input_rows": [],
                "comparison_metrics": [],
            },
            "logs": [],
            "error": None,
        },
    }


def test_pdf_generation(tmp_path: Path):
    """Test PDF generation with sample data"""

    # Sample conversation history
    csv_path = tmp_path / "la_population.csv"
    csv_path.write_text("NAME,B01003_001E\nLos Angeles,9848406\n", encoding="utf-8")

    conversation_history = [
        _sample_entry(
            generated_files=[
                {
                    "kind": "table",
                    "path": str(csv_path),
                    "mime_type": "text/csv",
                    "title": "Los Angeles Population",
                }
            ],
            census_data=_sample_census_data(),
        )
    ]

    # Test PDF generation
    try:
        pdf_bytes = generate_session_pdf(
            conversation_history=conversation_history,
            user_id="test_user",
            session_metadata={
                "thread_id": "test_thread",
            },
        )

        # ASSERTION 1: PDF generation should not raise an exception
        assert pdf_bytes is not None, "PDF generation returned None"

        # ASSERTION 2: PDF should be bytes data
        assert isinstance(pdf_bytes, bytes), f"Expected bytes, got {type(pdf_bytes)}"

        # ASSERTION 3: PDF should have reasonable size (not empty, not too large)
        assert len(pdf_bytes) > 1000, (
            f"PDF too small: {len(pdf_bytes)} bytes (expected > 1000)"
        )
        assert len(pdf_bytes) < 10_000_000, (
            f"PDF too large: {len(pdf_bytes)} bytes (expected < 10MB)"
        )

        # ASSERTION 4: PDF should start with PDF header
        assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF header: {pdf_bytes[:10]}"

        # Save test PDF
        test_pdf_path = tmp_path / "test_session_report.pdf"
        with open(test_pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # ASSERTION 5: File should be created successfully
        assert test_pdf_path.exists(), f"PDF file not created: {test_pdf_path}"

        # ASSERTION 6: File size should match bytes length
        file_size = test_pdf_path.stat().st_size
        assert file_size == len(pdf_bytes), (
            f"File size mismatch: {file_size} vs {len(pdf_bytes)}"
        )

    except Exception as e:
        pytest.fail(f"PDF generation failed: {e}")


def test_empty_conversation():
    """Test PDF generation with empty conversation history"""

    try:
        pdf_bytes = generate_session_pdf(
            conversation_history=[],
            user_id="test_user",
            session_metadata={
                "thread_id": "test_thread",
            },
        )

        # ASSERTION: Should still generate a PDF (cover page only)
        assert pdf_bytes is not None, "Empty conversation PDF generation returned None"
        assert isinstance(pdf_bytes, bytes), f"Expected bytes, got {type(pdf_bytes)}"
        assert len(pdf_bytes) > 500, f"Empty PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF header: {pdf_bytes[:10]}"

    except Exception as e:
        pytest.fail(f"Empty conversation PDF test failed: {e}")


def test_missing_files():
    """Test PDF generation with missing chart/table files"""

    conversation_history = [
        {
            "question": "Test question with missing files",
            "timestamp": datetime.now(),
            "result": {
                "final": {
                    "answer_text": "This is a test answer.",
                    "generated_files": [
                        {
                            "kind": "chart",
                            "path": "data/charts/nonexistent_chart.png",
                            "mime_type": "image/png",
                            "title": "Missing Chart",
                        },
                        {
                            "kind": "table",
                            "path": "data/tables/nonexistent_table.csv",
                            "mime_type": "text/csv",
                            "title": "Missing Table",
                        },
                    ],
                    "footnotes": [],
                    "charts_needed": [],
                    "tables_needed": [],
                },
                "artifacts": {
                    "census_data": _sample_census_data(),
                    "variable_labels": {"labels": {}},
                    "data_summary": "",
                    "reasoning_trace": "",
                    "comparison_input_rows": [],
                    "comparison_metrics": [],
                },
                "logs": [],
                "error": None,
            },
        }
    ]

    try:
        pdf_bytes = generate_session_pdf(
            conversation_history=conversation_history,
            user_id="test_user",
            session_metadata={
                "thread_id": "test_thread",
            },
        )

        # ASSERTION: Should still generate PDF even with missing files
        assert pdf_bytes is not None, "PDF generation with missing files returned None"
        assert isinstance(pdf_bytes, bytes), f"Expected bytes, got {type(pdf_bytes)}"
        assert len(pdf_bytes) > 500, (
            f"PDF with missing files too small: {len(pdf_bytes)} bytes"
        )
        assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF header: {pdf_bytes[:10]}"

    except Exception as e:
        pytest.fail(f"Missing files PDF test failed: {e}")


if __name__ == "__main__":
    print("🧪 Testing PDF Generation...")

    # Run all tests
    tests = [
        ("Basic PDF Generation", test_pdf_generation),
        ("Empty Conversation", test_empty_conversation),
        ("Missing Files", test_missing_files),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL PDF generation tests PASSED!")
        print("Ready to test in Streamlit!")
    else:
        print(f"\n💥 {total - passed} tests FAILED!")
        print("Check the errors above and fix issues.")
