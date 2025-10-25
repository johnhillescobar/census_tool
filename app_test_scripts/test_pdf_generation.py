"""
Test PDF generation functionality
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.utils.pdf_generator import generate_session_pdf


def test_pdf_generation():
    """Test PDF generation with sample data"""

    # Sample conversation history
    conversation_history = [
        {
            "question": "What's the population of Los Angeles?",
            "answer_text": "Los Angeles has a population of 9.8 million people according to the 2020 Census.",
            "generated_files": [
                "Chart created successfully: data/charts/chart_bar_20241201_143022.png",
                "Table created successfully: data/tables/la_population_20241201_143022.csv",
            ],
            "timestamp": pd.Timestamp.now(),
            "result": {
                "final": {
                    "answer_text": "Los Angeles has a population of 9.8 million people according to the 2020 Census.",
                    "generated_files": [
                        "Chart created successfully: data/charts/chart_bar_20241201_143022.png",
                        "Table created successfully: data/tables/la_population_20241201_143022.csv",
                    ],
                },
                "artifacts": {
                    "census_data": {
                        "data": [["NAME", "B01003_001E"], ["Los Angeles", "9848406"]],
                        "variables": {"B01003_001E": "Total Population"},
                    }
                },
            },
        }
    ]

    # Test PDF generation
    try:
        pdf_bytes = generate_session_pdf(
            conversation_history=conversation_history,
            user_id="test_user",
            session_metadata={
                "thread_id": "test_thread",
                "generated_at": datetime.now(),
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
        test_pdf_path = Path("test_session_report.pdf")
        with open(test_pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # ASSERTION 5: File should be created successfully
        assert test_pdf_path.exists(), f"PDF file not created: {test_pdf_path}"

        # ASSERTION 6: File size should match bytes length
        file_size = test_pdf_path.stat().st_size
        assert file_size == len(pdf_bytes), (
            f"File size mismatch: {file_size} vs {len(pdf_bytes)}"
        )

        print(f"✅ PDF generated successfully: {test_pdf_path}")
        print(f"📄 PDF size: {len(pdf_bytes)} bytes")
        print(f"📊 Conversations processed: {len(conversation_history)}")

        return True

    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        return False


def test_empty_conversation():
    """Test PDF generation with empty conversation history"""

    try:
        pdf_bytes = generate_session_pdf(
            conversation_history=[],
            user_id="test_user",
            session_metadata={
                "thread_id": "test_thread",
                "generated_at": datetime.now(),
            },
        )

        # ASSERTION: Should still generate a PDF (cover page only)
        assert pdf_bytes is not None, "Empty conversation PDF generation returned None"
        assert isinstance(pdf_bytes, bytes), f"Expected bytes, got {type(pdf_bytes)}"
        assert len(pdf_bytes) > 500, f"Empty PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF header: {pdf_bytes[:10]}"

        print("✅ Empty conversation PDF test PASSED")
        return True

    except Exception as e:
        print(f"❌ Empty conversation PDF test FAILED: {e}")
        return False


def test_missing_files():
    """Test PDF generation with missing chart/table files"""

    conversation_history = [
        {
            "question": "Test question with missing files",
            "answer_text": "This is a test answer.",
            "generated_files": [
                "Chart created successfully: data/charts/nonexistent_chart.png",
                "Table created successfully: data/tables/nonexistent_table.csv",
            ],
            "timestamp": pd.Timestamp.now(),
            "result": {
                "final": {
                    "answer_text": "This is a test answer.",
                    "generated_files": [
                        "Chart created successfully: data/charts/nonexistent_chart.png",
                        "Table created successfully: data/tables/nonexistent_table.csv",
                    ],
                },
                "artifacts": {
                    "census_data": {"data": [["NAME", "VALUE"], ["Test", "123"]]}
                },
            },
        }
    ]

    try:
        pdf_bytes = generate_session_pdf(
            conversation_history=conversation_history,
            user_id="test_user",
            session_metadata={
                "thread_id": "test_thread",
                "generated_at": datetime.now(),
            },
        )

        # ASSERTION: Should still generate PDF even with missing files
        assert pdf_bytes is not None, "PDF generation with missing files returned None"
        assert isinstance(pdf_bytes, bytes), f"Expected bytes, got {type(pdf_bytes)}"
        assert len(pdf_bytes) > 500, (
            f"PDF with missing files too small: {len(pdf_bytes)} bytes"
        )
        assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF header: {pdf_bytes[:10]}"

        print("✅ Missing files PDF test PASSED")
        return True

    except Exception as e:
        print(f"❌ Missing files PDF test FAILED: {e}")
        return False


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
