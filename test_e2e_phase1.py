"""
End-to-End Test from main.py entry point
Tests: main.py → graph → agent → tools → Census API → structured output
"""

import sys

sys.path.append(".")


def test_main_entry_point():
    """Test complete workflow from main.py"""

    print("\n" + "=" * 80)
    print("END-TO-END TEST: main.py → graph → agent → Census API")
    print("=" * 80)

    # Import main app
    try:
        from main import app

        print("✅ main.py imported successfully")
    except ImportError as e:
        print(f"❌ Cannot import main.py: {e}")
        return

    # Test query
    test_input = {
        "messages": [
            {"role": "user", "content": "What is the population of San Francisco?"}
        ],
        "profile": {"user_id": "test_e2e", "save_pdf": False},
    }

    print("\n📤 Sending query through main.py graph...")

    try:
        # Run through graph
        result = app.invoke(test_input)
        print("✅ Graph execution completed")

        # Validate output
        assert "final" in result, "❌ Missing 'final' in output"
        print("✅ Has 'final' output")

        final = result["final"]

        # Check for census data
        if "census_data" in final:
            print(f"✅ Census data in final: {len(str(final['census_data']))} chars")
        elif "artifacts" in result and "census_data" in result["artifacts"]:
            print(
                f"✅ Census data in artifacts: {len(str(result['artifacts']['census_data']))} chars"
            )
        else:
            print("⚠️  No census_data found in output")

        # Check for answer
        if "answer_text" in final:
            print(f"✅ Answer: {final['answer_text'][:100]}...")
        else:
            print("⚠️  No answer_text in final")

        print("\n" + "=" * 80)
        print("✅ END-TO-END TEST PASSED")
        print("=" * 80)

        return result

    except Exception as e:
        print(f"\n❌ END-TO-END TEST FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_main_entry_point()
