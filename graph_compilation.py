"""
Test graph compilation
"""

from app import create_census_graph


def test_graph_compilation():
    print("Testing graph compilation...")
    try:
        graph_compiled = create_census_graph()
        print(f"✅ Graph compiled successfully! {graph_compiled}")
        return True
    except Exception as e:
        print(f"❌ Graph compilation failed: {e}")
        return False


if __name__ == "__main__":
    test_graph_compilation()
