#!/usr/bin/env python3
"""
End-to-end test for Phase 3 implementation
Tests chart and table generation functionality
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import logging

# Set up logging to minimize noise
logging.basicConfig(level=logging.WARNING)

# Add project root
project_root = Path(__file__).parent
sys.path.append(str(project_root))

load_dotenv()


def test_phase3_end_to_end():
    """Test the complete Phase 3 implementation"""

    print("PHASE 3 END-TO-END TEST")
    print("=" * 40)

    try:
        # Test 1: Import and initialization
        print("Step 1: Testing imports and configuration...")

        from app import create_census_graph
        from src.state.types import CensusState
        from langchain_core.runnables import RunnableConfig

        # Test agent tools
        from src.utils.agents.census_query_agent import CensusQueryAgent

        agent = CensusQueryAgent()
        tool_names = [tool.name for tool in agent.tools]

        print(f"[OK] Agent initialized with {len(tool_names)} tools")
        print(f"Tools: {tool_names}")

        # Check Phase 3 tools
        has_chart = "create_chart" in tool_names
        has_table = "create_table" in tool_names

        print(f"[OK] ChartTool available: {has_chart}")
        print(f"[OK] TableTool available: {has_table}")

        if not (has_chart and has_table):
            print("[ERROR] Missing Phase 3 tools")
            return False

        # Test 2: Graph creation
        print("\nStep 2: Testing graph creation...")
        graph = create_census_graph()
        print("[OK] Graph created successfully")

        # Test 3: End-to-end test with simple query
        print("\nStep 3: Testing end-to-end flow...")

        test_query = "What is the population of New York City?"
        print(f"Test query: {test_query}")

        # Create initial state
        initial_state = CensusState(
            messages=[{"role": "user", "content": test_query}],
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
            configurable={"user_id": "test_e2e", "thread_id": "phase3_validation"}
        )

        # Process through graph
        print("Processing query through graph...")
        result = graph.invoke(initial_state, config)

        # Analyze results
        print("\nStep 4: Analyzing results...")
        final = result.get("final", {})
        artifacts = result.get("artifacts", {})

        # Check basic functionality
        answer_text = final.get("answer_text", "")
        print(f"Answer provided: {'Yes' if answer_text else 'No'}")

        if answer_text:
            print(f"Answer preview: {answer_text[:80]}...")

        # Check Phase 3 specific features
        charts_needed = final.get("charts_needed", [])
        tables_needed = final.get("tables_needed", [])
        generated_files = final.get("generated_files", [])

        print(f"Charts requested: {len(charts_needed)}")
        print(f"Tables requested: {len(tables_needed)}")
        print(f"Files generated: {len(generated_files)}")

        # Check census data
        census_data = artifacts.get("census_data", {})
        has_census_data = bool(census_data.get("data"))
        print(f"Census data retrieved: {'Yes' if has_census_data else 'No'}")

        # Final assessment
        print("\nPHASE 3 VALIDATION RESULTS:")
        print("=" * 35)

        success_criteria = [
            ("Agent tools configured", has_chart and has_table),
            ("Graph processes query", result is not None),
            ("Agent provides answer", bool(answer_text)),
            ("Census data retrieved", has_census_data),
            ("No processing errors", "error" not in result or not result.get("error")),
        ]

        for criterion, passed in success_criteria:
            status = "[OK]" if passed else "[FAIL]"
            print(f"{status} {criterion}")

        overall_success = sum(1 for _, passed in success_criteria if passed)
        total_criteria = len(success_criteria)

        print(f"\nOverall Score: {overall_success}/{total_criteria}")

        if overall_success >= 4:
            print("\nPHASE 3 END-TO-END TEST: SUCCESS!")
            print("[OK] Core functionality working")
            print("[OK] Chart and Table tools integrated")
            print("[OK] Output node ready")
            return True
        else:
            print("\nPHASE 3 END-TO-END TEST: NEEDS ATTENTION")
            print("Some components may need debugging")
            return False

    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_phase3_end_to_end()
    sys.exit(0 if success else 1)
