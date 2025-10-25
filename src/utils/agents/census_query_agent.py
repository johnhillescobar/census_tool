import os
import sys
import re
import logging
import json
from typing import Dict
from dotenv import load_dotenv

from langchain.agents.agent import AgentExecutor

# Try to import the agent creation function for different LangChain versions
try:
    from langchain.agents import create_react_agent
except ImportError:
    try:
        from langchain.agents import create_tool_calling_agent as create_react_agent
    except ImportError:
        # Last resort: create a fallback
        create_react_agent = None
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.llm.config import LLM_CONFIG, AGENT_PROMPT_TEMPLATE
from src.tools.geography_discovery_tool import GeographyDiscoveryTool
from src.tools.table_search_tool import TableSearchTool
from src.tools.census_api_tool import CensusAPITool
from src.tools.chart_tool import ChartTool
from src.tools.table_tool import TableTool
from src.tools.table_validation_tool import TableValidationTool
from src.tools.pattern_builder_tool import PatternBuilderTool
from src.tools.area_resolution_tool import AreaResolutionTool

load_dotenv()

logger = logging.getLogger(__name__)


class CensusQueryAgent:
    """
    Reasoning agent for Census queries
    Uses ReAct pattern with Census tools
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature"]
        )

        # Initialize tools
        self.tools = [
            GeographyDiscoveryTool(),
            TableSearchTool(),
            CensusAPITool(),
            TableTool(),
            TableValidationTool(),
            PatternBuilderTool(),
            AreaResolutionTool(),
            ChartTool(),
        ]

        # Create agent with compatibility for different LangChain versions
        if create_react_agent is None:
            raise ImportError(
                "No compatible agent creation function available. Please update LangChain or use a different version."
            )

        self.agent = create_react_agent(
            llm=self.llm, tools=self.tools, prompt=self._build_prompt()
        )

        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=15,
            handle_parsing_errors="Check your output format. You must output: 'Thought: I now know the final answer' followed by 'Final Answer: {valid JSON on single line}'",
        )

    def _build_prompt(self):
        return PromptTemplate.from_template(AGENT_PROMPT_TEMPLATE)

    def solve(self, user_query: str, intent: Dict) -> Dict:
        """
        Reason through the query and return structured data
        """
        result = self.agent_executor.invoke(
            {
                "input": f"""User query: {user_query}
Intent: {intent}"""
            }
        )

        return self._parse_solution(result)

    def _parse_solution(self, result: Dict) -> Dict:
        """
        Parse agent output into structured format.
        Extract the JSON from the ReAct agent's Final Answer.
        """
        output = result.get("output", "")
        logger.info(f"Parsing agent output (length: {len(output)} chars)")
        logger.debug(f"Output first 200 chars: {output[:200]}...")

        # Method 1: LangChain agent executor returns final answer directly in output
        # Try to parse the entire output as JSON first
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict) and "census_data" in parsed:
                logger.info("Successfully parsed agent output as JSON directly")
                return parsed
            else:
                logger.debug(
                    f"Parsed JSON but missing census_data key. Keys: {parsed.keys() if isinstance(parsed, dict) else 'not a dict'}"
                )
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Output is not direct JSON: {e}")

        # Find all potential JSON matches
        potential_jsons = []

        # Try to find JSON on single line first (most common with new prompt)
        single_line_match = re.search(
            r'\{[^{}]*"census_data"[^{}]*(?:\{(?:[^{}]*|\{[^{}]*\})*\}[^{}]*)*\}',
            output,
        )
        if single_line_match:
            potential_jsons.append(single_line_match.group(0))

        # Also try splitting and looking for JSON blocks
        if '{"census_data"' in output:
            start_idx = output.find('{"census_data"')
            if start_idx != -1:
                # Find the matching closing brace
                brace_count = 0
                end_idx = start_idx
                for i, char in enumerate(output[start_idx:], start=start_idx):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break

                if end_idx > start_idx:
                    potential_jsons.append(output[start_idx:end_idx])

        # Try parsing each potential JSON
        for json_str in potential_jsons:
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and "census_data" in parsed:
                    logger.info("Successfully extracted and parsed agent JSON")
                    return parsed
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to parse JSON candidate: {e}")
                continue

        # Method 3: Try to extract from intermediate_steps as fallback
        intermediate_steps = result.get("intermediate_steps", [])
        for step in reversed(intermediate_steps):
            if isinstance(step, dict) and "tool_output" in step:
                tool_output = step["tool_output"]
                if isinstance(tool_output, str):
                    try:
                        parsed_output = json.loads(tool_output)
                        if (
                            isinstance(parsed_output, dict)
                            and parsed_output.get("success")
                            and "data" in parsed_output
                        ):
                            census_result = parsed_output["data"]
                            if (
                                isinstance(census_result, dict)
                                and "data" in census_result
                            ):
                                # Extract first data row for simple fallback
                                census_data_rows = census_result["data"]
                                if len(census_data_rows) > 1:
                                    headers = census_data_rows[0]
                                    data_row = census_data_rows[1]
                                    census_dict = dict(zip(headers, data_row))

                                    return {
                                        "census_data": {
                                            "data": census_data_rows,
                                            "variables": {
                                                "B01003_001E": "Total Population"
                                            },
                                        },
                                        "data_summary": f"Retrieved Census data for {census_dict.get('NAME', 'location')}",
                                        "reasoning_trace": "Data extracted from agent's tool execution",
                                        "answer_text": f"Population: {census_dict.get('B01003_001E', 'N/A')}",
                                    }
                    except (json.JSONDecodeError, TypeError, IndexError, KeyError):
                        continue

        # Method 4: If all else fails, return empty structure but log the issue
        logger.warning(
            "Agent did not return valid JSON - agent may have hit iteration limit"
        )
        logger.debug(f"Raw output (first 500 chars): {output[:500]}...")

        return {
            "census_data": {},
            "data_summary": "Agent execution completed but no parseable JSON found",
            "reasoning_trace": f"Execution steps: {len(intermediate_steps)}",
            "answer_text": "Agent execution completed but output parsing failed",
        }
