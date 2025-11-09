"""
Test that agent doesn't loop forever when validation fails.
"""
from src.utils.agents.census_query_agent import CensusQueryAgent


def test_agent_returns_error_on_iteration_limit():
    """Agent should return clear error instead of looping forever"""
    agent = CensusQueryAgent()
    
    # Simulate a query that would cause validation loop
    # (This will be a real test once we implement the fallback)
    result = agent.solve(
        "What's the population of Mars?",  # Invalid geography
        {"is_census": True, "topic": "general"}
    )
    
    # Should get error response, not loop forever
    assert result["census_data"]["success"] is False
    assert "unable to complete" in result["answer_text"].lower() or "not available" in result["answer_text"].lower()

