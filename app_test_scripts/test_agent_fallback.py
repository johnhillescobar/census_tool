"""
Test that agent doesn't loop forever when validation fails.
"""

from unittest.mock import MagicMock, patch
import os
from src.utils.agents.census_query_agent import CensusQueryAgent


def test_agent_returns_error_on_iteration_limit():
    """Agent should return clear error instead of looping forever"""
    # Mock OPENAI_API_KEY and LLM creation so agent initializes properly without real credentials
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        with patch("src.utils.agents.census_query_agent.create_llm") as mock_create_llm:
            mock_create_llm.return_value = MagicMock()
            agent = CensusQueryAgent(allow_offline=False)

            # Mock the agent_executor to simulate invalid geography scenario
            # This simulates what happens when resolve_area_name fails
            mock_result = {
                "output": '{"census_data":{"success":false,"data":[]},"data_summary":"No Census data exists for Mars","reasoning_trace":"Recognized Mars is not a U.S. geography","answer_text":"Mars has a population of 0; there are no permanent human residents.","charts_needed":[],"tables_needed":[],"footnotes":[]}',
                "intermediate_steps": [
                    (
                        MagicMock(
                            tool="resolve_area_name",
                            tool_input='{"name":"Mars","geography_type":"state"}',
                        ),
                        "No match found for 'Mars' in state",  # This is the error message format
                    )
                ],
            }

            agent.agent_executor = MagicMock()
            agent.agent_executor.invoke = MagicMock(return_value=mock_result)

            result = agent.solve(
                "What's the population of Mars?",  # Invalid geography
                {"is_census": True, "topic": "general"},
            )

            # Should get error response, not loop forever
            assert result["census_data"]["success"] is False
            assert (
                "unable to complete" in result["answer_text"].lower()
                or "not available" in result["answer_text"].lower()
            )
