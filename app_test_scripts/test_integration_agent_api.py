"""
Integration tests for CensusQueryAgent with real Census API calls.
Tests end-to-end workflows from user query to final answer.

NOTE: These tests require real API keys and can be flaky in CI environments.
They are skipped by default in GitHub Actions - run locally with API keys configured.
"""

import pytest
import os
from unittest.mock import patch
from src.utils.agents.census_query_agent import CensusQueryAgent
from src.llm.config import LLM_CONFIG


# Skip these tests if no Census API key is available OR if running in CI
skip_in_ci = os.getenv("CI") or os.getenv("GITHUB_ACTIONS")
requires_api_key = pytest.mark.skipif(
    not os.getenv("CENSUS_API_KEY") or skip_in_ci,
    reason="Census API key not configured or running in CI (skipped for reliability)",
)


class TestAgentIntegration:
    """Integration tests with real Census API calls."""

    @requires_api_key
    @pytest.mark.integration
    def test_agent_state_population_query(self):
        """Test complete agent flow: question → API call → parse → answer."""
        agent = CensusQueryAgent()
        result = agent.solve(
            user_query="What is the population of California?",
            intent={"is_census": True, "topic": "population"},
        )

        # Verify structure
        assert "census_data" in result
        assert "answer_text" in result
        assert "footnotes" in result

        # Verify data was fetched
        assert result["census_data"].get("success") is True
        census_data = result["census_data"].get("data", [])
        assert len(census_data) >= 2  # Headers + at least one row

        # Verify California is mentioned
        assert "California" in result["answer_text"] or "CA" in str(census_data)

        # Verify footnotes were generated
        assert len(result["footnotes"]) >= 2
        assert any("Census" in note for note in result["footnotes"])

    @requires_api_key
    @pytest.mark.integration
    def test_agent_multiple_states_query(self):
        """Test agent can handle multi-state comparisons."""
        agent = CensusQueryAgent()
        result = agent.solve(
            user_query="Compare population of California, Texas, and Florida",
            intent={"is_census": True, "topic": "population", "geography": "state"},
        )

        assert "census_data" in result
        assert result["census_data"].get("success") is True

        census_data = result["census_data"].get("data", [])
        assert len(census_data) >= 4  # Headers + 3 states

        # Should have chart for comparison
        assert len(result.get("charts_needed", [])) >= 1
        assert result["charts_needed"][0]["type"] == "bar"

    @requires_api_key
    @pytest.mark.integration
    def test_agent_handles_county_query_without_overwhelming_data(self):
        """
        Test agent can handle multi-county queries without fetching excessive data.
        This is the key test for the optimization - we don't want entire CP03 groups.
        """
        agent = CensusQueryAgent()
        result = agent.solve(
            user_query="List population for all counties in Delaware",
            intent={"is_census": True, "topic": "population", "geography": "county"},
        )

        # Should have census data
        assert "census_data" in result
        assert result["census_data"].get("success") is True

        data = result["census_data"].get("data", [])
        if len(data) > 0:
            # Check that we don't have excessive columns
            # Population query should have just a few columns (NAME, population, maybe state/county codes)
            # NOT 100+ variables like full CP03
            num_columns = len(data[0])
            assert num_columns < 20, (
                f"Too many variables fetched ({num_columns} columns). "
                f"For simple population query, should be < 20 columns, not entire table group."
            )

        # Should have answer text
        assert len(result["answer_text"]) > 50
        assert (
            "Delaware" in result["answer_text"]
            or "county" in result["answer_text"].lower()
        )

    @requires_api_key
    @pytest.mark.integration
    @pytest.mark.slow
    def test_agent_parses_large_multi_county_response(self):
        """
        Test parsing of large response (many counties).
        Uses a state with many counties to test parsing robustness.
        """
        # Increase timeout for this test to handle large streaming responses
        from src.llm.factory import _create_openai_llm

        original_create_openai_llm = _create_openai_llm

        def create_openai_llm_with_timeout(model, temperature, **kwargs):
            # Force timeout=120 by patching LLM_CONFIG temporarily
            with patch.dict(LLM_CONFIG, {"timeout": 120}, clear=False):
                return original_create_openai_llm(model, temperature, **kwargs)

        with patch(
            "src.llm.factory._create_openai_llm",
            side_effect=create_openai_llm_with_timeout,
        ):
            agent = CensusQueryAgent()
            result = agent.solve(
                user_query="Show population for all counties in Texas",
                intent={
                    "is_census": True,
                    "topic": "population",
                    "geography": "county",
                },
            )

            # Texas has 254 counties - this is a large response
            assert "census_data" in result
            assert result["census_data"].get("success") is True

            data = result["census_data"].get("data", [])
            # Should have headers + many county rows
            assert len(data) > 200, (
                f"Expected 250+ rows for Texas counties, got {len(data)}"
            )

        # Verify parsing succeeded
        assert (
            result["answer_text"]
            != "Agent execution completed but output parsing failed"
        )
        assert "census_data" in result

        # Should mention Texas
        assert "Texas" in result["answer_text"] or "TX" in str(data)

    @requires_api_key
    @pytest.mark.integration
    def test_agent_handles_table_search_workflow(self):
        """Test agent can find appropriate table for user's topic."""
        agent = CensusQueryAgent()
        result = agent.solve(
            user_query="What is the median household income in California?",
            intent={"is_census": True, "topic": "income"},
        )

        assert "census_data" in result
        assert result["census_data"].get("success") is True

        # Should mention income in answer
        assert any(
            word in result["answer_text"].lower()
            for word in ["income", "median", "household"]
        )

        # Should reference appropriate table in footnotes
        footnotes_text = " ".join(result.get("footnotes", []))
        assert "table" in footnotes_text.lower() or "B19013" in footnotes_text

    @requires_api_key
    @pytest.mark.integration
    def test_agent_generates_charts_and_tables(self):
        """Test agent properly specifies charts and tables in output."""
        # Increase timeout for this test to handle large streaming responses
        # Patch _create_openai_llm to force timeout=120 in ChatOpenAI initialization
        from src.llm.factory import _create_openai_llm

        original_create_openai_llm = _create_openai_llm

        def create_openai_llm_with_timeout(model, temperature, **kwargs):
            # Force timeout=120 by patching LLM_CONFIG temporarily
            with patch.dict(LLM_CONFIG, {"timeout": 120}, clear=False):
                return original_create_openai_llm(model, temperature, **kwargs)

        with patch(
            "src.llm.factory._create_openai_llm",
            side_effect=create_openai_llm_with_timeout,
        ):
            agent = CensusQueryAgent()
            result = agent.solve(
                user_query="Compare population of the 5 largest states and export to CSV",
                intent={"is_census": True, "topic": "population"},
            )

            # Should specify chart for comparison
            assert len(result.get("charts_needed", [])) >= 1
            assert result["charts_needed"][0]["type"] in ["bar", "line"]

            # Should specify table export
            assert len(result.get("tables_needed", [])) >= 1
            assert result["tables_needed"][0]["format"] == "csv"

    @requires_api_key
    @pytest.mark.integration
    def test_agent_validates_geography_support(self):
        """Test agent validates table supports requested geography."""
        # Increase timeout for this test to handle large streaming responses
        # Patch _create_openai_llm to force timeout=120 in ChatOpenAI initialization
        from src.llm.factory import _create_openai_llm

        original_create_openai_llm = _create_openai_llm

        def create_openai_llm_with_timeout(model, temperature, **kwargs):
            # Force timeout=120 by patching LLM_CONFIG temporarily
            with patch.dict(LLM_CONFIG, {"timeout": 120}, clear=False):
                return original_create_openai_llm(model, temperature, **kwargs)

        with patch(
            "src.llm.factory._create_openai_llm",
            side_effect=create_openai_llm_with_timeout,
        ):
            agent = CensusQueryAgent()

            # Valid query - states support most tables
            result = agent.solve(
                user_query="Population of all states",
                intent={"is_census": True, "topic": "population", "geography": "state"},
            )

            assert result["census_data"].get("success") is True
            assert "error" not in result["answer_text"].lower()


class TestAgentErrorHandling:
    """Test agent handles various error conditions gracefully."""

    @requires_api_key
    @pytest.mark.integration
    def test_agent_handles_ambiguous_query(self):
        """Test agent handles vague or ambiguous queries."""
        # Increase timeout for this test to handle large streaming responses
        from src.llm.factory import _create_openai_llm

        original_create_openai_llm = _create_openai_llm

        def create_openai_llm_with_timeout(model, temperature, **kwargs):
            # Force timeout=120 by patching LLM_CONFIG temporarily
            with patch.dict(LLM_CONFIG, {"timeout": 120}, clear=False):
                return original_create_openai_llm(model, temperature, **kwargs)

        with patch(
            "src.llm.factory._create_openai_llm",
            side_effect=create_openai_llm_with_timeout,
        ):
            agent = CensusQueryAgent()
            result = agent.solve(
                user_query="Tell me about demographics",
                intent={"is_census": True, "topic": "general"},
            )

            # Should still produce some response (even if limited)
            assert "answer_text" in result
            assert len(result["answer_text"]) > 20

    def test_agent_handles_invalid_geography(self):
        """Test agent handles invalid geography names gracefully."""
        agent = CensusQueryAgent()
        result = agent.solve(
            user_query="Population of Atlantis County",
            intent={"is_census": True, "topic": "population"},
        )

        # Should not crash - may have empty data or error message
        assert "answer_text" in result
        # Result should acknowledge the issue
        assert result["census_data"].get("success") in [True, False]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
