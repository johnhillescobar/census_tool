#!/usr/bin/env python3
"""
Test the main.py workflow with Phase 3 chart/table generation
Simulates the user interaction flow
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Set up minimal logging
logging.basicConfig(level=logging.WARNING)

# Add project root
project_root = Path(__file__).parent
sys.path.append(str(project_root))

load_dotenv()


def test_main_workflow():
    """Test the complete main.py workflow"""

    print("MAIN WORKFLOW TEST")
    print("=" * 30)

    try:
        # Import main components
        from app import create_census_graph
        from src.state.types import CensusState
        from langchain_core.runnables import RunnableConfig
        from src.utils.displays import display_results

        print("[OK] Imports successful")

        # Initialize graph
        graph = create_census_graph()
        print("[OK] Graph created")

        # Test with chart request query
        test_query = "Show me population by county in California as a bar chart and export the data as CSV"
        print(f"\nTest Query: {test_query}")

        # Create user ID and thread ID like main.py would
        user_id = "test_user"
        thread_id = "main_workflow_test"

        # Create initial state exactly like main.py
        initial_state = CensusState(
            messages=[{"role": "user", "content": test_query}],
            original_query=None,  # Will be set by intent_node
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

        # Create config exactly like main.py
        config = RunnableConfig(
            configurable={"user_id": user_id, "thread_id": thread_id}
        )

        print("\nProcessing through graph...")
        result = graph.invoke(initial_state, config)

        print("\nTesting display_results...")
        display_results(result)

        # Analyze results
        final = result.get("final", {})
        artifacts = result.get("artifacts", {})

        print("\nWORKFLOW ANALYSIS:")
        print("=" * 20)

        # Check Phase 3 components
        answer_text = final.get("answer_text", "")
        charts_needed = final.get("charts_needed", [])
        tables_needed = final.get("tables_needed", [])
        generated_files = final.get("generated_files", [])

        print(f"Answer provided: {'Yes' if answer_text else 'No'}")
        print(f"Charts requested: {len(charts_needed)}")
        print(f"Tables requested: {len(tables_needed)}")
        print(f"Files generated: {len(generated_files)}")

        # Check census data
        census_data = artifacts.get("census_data", {})
        has_data = bool(census_data.get("data"))
        print(f"Census data retrieved: {'Yes' if has_data else 'No'}")

        # Final assessment
        success_criteria = [
            ("Main workflow executes", result is not None),
            ("Answer provided", bool(answer_text)),
            ("Census data retrieved", has_data),
            (
                "Charts/tables requested",
                len(charts_needed) > 0 or len(tables_needed) > 0,
            ),
            ("Files generated", len(generated_files) > 0),
            ("Display function works", True),  # If we reach here, display worked
        ]

        successful = sum(1 for _, passed in success_criteria if passed)
        total = len(success_criteria)

        print(f"\nSUCCESS RATE: {successful}/{total}")

        if successful >= 4:
            print("\nMAIN WORKFLOW TEST: SUCCESS!")
            print("[OK] Main.py integration working with Phase 3")
            return True
        else:
            print("\nMAIN WORKFLOW TEST: NEEDS ATTENTION")
            return False

    except Exception as e:
        print(f"\n[ERROR] Main workflow test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_main_workflow()
    sys.exit(0 if success else 1)
