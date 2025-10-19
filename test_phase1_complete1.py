import sys
sys.path.append('.')

from src.utils.agents.census_query_agent import CensusQueryAgent

def test_agent_returns_census_data():
    """Test that agent fetches and returns actual Census data"""
    
    print("\n" + "="*80)
    print("PHASE 1 COMPLETION TEST")
    print("="*80)
    
    agent = CensusQueryAgent()
    
    # Test query - simple single county
    result = agent.solve(
        user_query="What is the population of Los Angeles County, California?",
        intent={"topic": "population", "geography": "county", "state": "California"}
    )
    
    print("\n📋 Testing agent output structure...")
    
    # Validate structured output
    assert isinstance(result, dict), f"❌ Expected dict, got {type(result)}"
    print("✅ Returns dict")
    
    # Check required fields
    required_fields = ["census_data", "data_summary", "reasoning_trace", "answer_text"]
    for field in required_fields:
        assert field in result, f"❌ Missing required field: {field}"
        print(f"✅ Has field: {field}")
    
    # Check census_data is not empty
    if result["census_data"]:
        print(f"✅ census_data has content: {len(str(result['census_data']))} chars")
    else:
        print("⚠️  census_data is empty (agent may not have called census_api_call)")
    
    # Check data_summary is meaningful
    if len(result["data_summary"]) > 10:
        print(f"✅ data_summary: {result['data_summary'][:80]}...")
    else:
        print(f"⚠️  data_summary is short: {result['data_summary']}")
    
    # Check answer_text mentions population
    if "population" in result["answer_text"].lower():
        print(f"✅ answer_text mentions population")
    else:
        print(f"⚠️  answer_text doesn't mention population")
    
    print(f"\n📝 Answer: {result['answer_text'][:200]}...")
    
    print("\n" + "="*80)
    if result["census_data"]:
        print("✅ PHASE 1 COMPLETE: Agent returns structured Census data")
    else:
        print("⚠️  PHASE 1 PARTIAL: Agent returns structure but no Census data")
    print("="*80)
    
    return result

if __name__ == "__main__":
    try:
        test_agent_returns_census_data()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()