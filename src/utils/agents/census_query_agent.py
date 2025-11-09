import os
import sys
import logging
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from langchain.agents import AgentExecutor

# Try to import the agent creation function for different LangChain versions
try:
    from langchain.agents import create_react_agent
except ImportError:
    try:
        from langchain.agents import create_tool_calling_agent as create_react_agent
    except ImportError:
        # Last resort: create a fallback
        create_react_agent = None
from langchain.prompts import PromptTemplate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.llm.config import LLM_CONFIG, AGENT_PROMPT_TEMPLATE
from src.llm.factory import create_llm
from src.tools.geography_discovery_tool import GeographyDiscoveryTool
from src.tools.geography_hierarchy_tool import GeographyHierarchyTool
from src.tools.table_search_tool import TableSearchTool
from src.tools.census_api_tool import CensusAPITool
from src.tools.chart_tool import ChartTool
from src.tools.table_tool import TableTool
from src.tools.table_validation_tool import TableValidationTool
from src.tools.pattern_builder_tool import PatternBuilderTool
from src.tools.area_resolution_tool import AreaResolutionTool
from src.tools.variable_validation_tool import VariableValidationTool

load_dotenv()

logger = logging.getLogger(__name__)


class CensusData(BaseModel):
    success: bool
    data: List[List[Any]]
    variables: Optional[Dict[str, str]] = None


class AgentOutput(BaseModel):
    census_data: CensusData
    data_summary: str
    reasoning_trace: str
    answer_text: str
    charts_needed: List[Dict[str, str]] = []
    tables_needed: List[Dict[str, str]] = []
    footnotes: List[str] = []


class CensusQueryAgent:
    """
    Reasoning agent for Census queries
    Uses ReAct pattern with Census tools
    """

    def __init__(self):
        self.llm = create_llm(temperature=LLM_CONFIG["temperature"])

        # Initialize tools
        self.tools = [
            GeographyDiscoveryTool(),
            TableSearchTool(),
            CensusAPITool(),
            TableTool(),
            # TableValidationTool(),  # REMOVED - validation happens at API level
            PatternBuilderTool(),
            AreaResolutionTool(),
            ChartTool(),
            GeographyHierarchyTool(),
            VariableValidationTool(),
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
            max_iterations=30,
            max_execution_time=180,
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

    def _did_reach_iteration_limit(self, result: Dict, output: str) -> bool:
        """Check if agent exhausted iterations or time without completing."""
        intermediate_steps = result.get("intermediate_steps", [])
        
        # Hit max_iterations (30) or max_execution_time (180s)
        if len(intermediate_steps) >= 28:  # Close to limit
            return True
        
        # Check for repetitive tool calls (stuck in loop)
        if len(intermediate_steps) >= 10:
            recent_tools = [step[0].tool for step in intermediate_steps[-10:]]
            # If same tool called 5+ times in last 10 steps, likely stuck
            if any(recent_tools.count(tool) >= 5 for tool in set(recent_tools)):
                return True
        
        return False

    def _build_iteration_limit_response(self, result: Dict, output: str) -> Dict:
        """Build error response when agent gets stuck."""
        intermediate_steps = result.get("intermediate_steps", [])
        recent_actions = [
            f"{step[0].tool}({step[0].tool_input[:50]}...)" 
            for step in intermediate_steps[-5:]
        ]
        
        return {
            "census_data": {"success": False, "data": []},
            "data_summary": "Agent exceeded iteration limit",
            "reasoning_trace": f"Agent made {len(intermediate_steps)} attempts. Recent: {recent_actions}",
            "answer_text": "I was unable to complete this query due to repeated validation failures. The Census API may not support this specific combination of table, geography, and year. Please try rephrasing your question or requesting a different geography level (e.g., state instead of county).",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [
                "This query exceeded the maximum number of processing attempts.",
                "Try simplifying your request or using a more common geography level."
            ]
        }

    def _parse_solution(self, result: Dict) -> Dict:
        """
        Parse agent output - extract JSON after 'Final Answer:' prefix.
        Simplified to 2 methods: direct parse or prefix extraction.
        """
        output = result.get("output", "")
        if self._did_reach_iteration_limit(result, output):
            return self._build_iteration_limit_response(result, output)
        if not output:
            return self._build_empty_output_response(result)
        logger.info(f"Parsing agent output (length: {len(output)} chars)")

        # Method 1: Direct JSON parse (when AgentExecutor strips prefix)
        parsed = self._try_direct_json_parse(output)
        if parsed:
            return parsed

        # Method 2: Extract after "Final Answer:" prefix
        parsed = self._extract_after_final_answer(output)
        if parsed:
            return parsed

        # Fallback: Return empty structure with diagnostics
        logger.warning("All parsing methods failed")
        logger.debug(f"Raw output sample: {output[:500]}")

        intermediate_steps = result.get("intermediate_steps", [])
        return {
            "census_data": {},
            "data_summary": "Parsing failed - see logs",
            "reasoning_trace": f"Steps: {len(intermediate_steps)}",
            "answer_text": "Agent execution completed but output parsing failed",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }

    def _try_direct_json_parse(self, output: str) -> Optional[Dict]:
        """Attempt direct JSON parsing of entire output."""
        try:
            logger.error(
                f"[PARSE DEBUG] Attempting direct JSON parse. Output length: {len(output)}, first 200 chars: {output[:200]}"
            )
            parsed = json.loads(output)
            logger.error(
                f"[PARSE DEBUG] json.loads() succeeded. Type: {type(parsed)}, has census_data: {'census_data' in parsed if isinstance(parsed, dict) else 'N/A'}"
            )
            if isinstance(parsed, dict) and "census_data" in parsed:
                logger.error("[PARSE DEBUG] Attempting Pydantic validation...")
                validated = AgentOutput(**parsed)  # Pydantic validation
                logger.info("Successfully parsed as direct JSON")
                return validated.model_dump()
            else:
                logger.error(
                    f"[PARSE DEBUG] Direct parse - parsed but missing census_data. Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}"
                )
        except json.JSONDecodeError as e:
            logger.error(f"[PARSE DEBUG] Direct parse JSONDecodeError: {str(e)[:300]}")
        except ValidationError as e:
            logger.error(
                f"[PARSE DEBUG] Direct parse Pydantic ValidationError: {str(e)[:500]}"
            )
        except Exception as e:
            logger.error(
                f"[PARSE DEBUG] Direct parse unexpected error: {type(e).__name__}: {str(e)[:300]}"
            )
        return None

    def _build_empty_output_response(self, result: Dict) -> Dict[str, Any]:
        intermediate_steps = result.get("intermediate_steps", []) or []
        step_count = len(intermediate_steps)

        last_tool = None
        last_observation = None
        if intermediate_steps:
            last_step = intermediate_steps[-1]
            if isinstance(last_step, (tuple, list)) and len(last_step) == 2:
                action, observation = last_step
                last_tool = getattr(action, "tool", None)
                last_observation = observation

        summary_parts = [
            f"The agent completed {step_count} tool steps but did not emit a final answer payload."
        ]
        if last_tool:
            summary_parts.append(f"Last tool invoked: {last_tool}.")
        if last_observation:
            summary_parts.append("Review the session log for the final tool output.")

        data_summary = " ".join(summary_parts)
        answer_text = (
            "I gathered intermediate results but the response formatter did not run. "
            "Please rerun the question and I will try again."
        )

        census_data_payload: Dict[str, Any] = {"success": False, "error": "empty_output"}
        observation_dict = self._coerce_observation_to_dict(last_observation)
        if observation_dict and isinstance(observation_dict, dict):
            census_data_payload = observation_dict

        return {
            "census_data": census_data_payload,
            "data_summary": data_summary,
            "reasoning_trace": f"No final output after {step_count} steps.",
            "answer_text": answer_text,
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }

    def _did_reach_iteration_limit(self, result: Dict, output: str) -> bool:
        if not output:
            return False

        text = output.lower()
        if "agent stopped due to iteration limit" in text:
            return True
        if "agent stopped due to time limit" in text:
            return True

        error = result.get("error")
        if isinstance(error, str):
            lowered = error.lower()
            if "iteration limit" in lowered or "time limit" in lowered:
                return True
        return False

    def _build_iteration_limit_response(self, result: Dict, output: str) -> Dict[str, Any]:
        intermediate_steps = result.get("intermediate_steps", []) or []
        step_count = len(intermediate_steps)

        last_tool = None
        last_observation = None
        if intermediate_steps:
            last_step = intermediate_steps[-1]
            if isinstance(last_step, (tuple, list)) and len(last_step) == 2:
                action, observation = last_step
                last_tool = getattr(action, "tool", None)
                last_observation = observation

        summary_parts = [
            f"Stopped after {step_count} steps because the agent hit its iteration limit."
        ]
        if last_tool:
            summary_parts.append(f"Last tool invoked: {last_tool}.")
        if last_observation:
            summary_parts.append("Review the session log for the final tool output.")

        data_summary = " ".join(summary_parts)
        answer_text = (
            "I gathered data but reached the reasoning step limit before formatting the final answer. "
            "Please rerun the question or adjust it and I will try again."
        )

        census_data_payload: Dict[str, Any] = {"success": False, "error": "iteration_limit"}
        observation_dict = self._coerce_observation_to_dict(last_observation)
        if observation_dict and isinstance(observation_dict, dict):
            census_data_payload = observation_dict

        return {
            "census_data": census_data_payload,
            "data_summary": data_summary,
            "reasoning_trace": f"Iteration limit reached after {step_count} steps.",
            "answer_text": answer_text,
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
        }

    def _coerce_observation_to_dict(self, observation: Any) -> Optional[Dict[str, Any]]:
        if isinstance(observation, dict):
            return observation
        if isinstance(observation, str):
            text = observation.strip()
            if text.startswith("{") and text.endswith("}"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    return None
        return None

    def _extract_after_final_answer(self, output: str) -> Optional[Dict]:
        """Extract JSON after 'Final Answer:' prefix using state machine."""
        # Find "Final Answer:" marker
        marker = "Final Answer:"
        idx = output.find(marker)
        if idx == -1:
            logger.error(
                f"[PARSE DEBUG] No 'Final Answer:' marker found. Output length: {len(output)}, First 300 chars: {output[:300]}"
            )
            return None

        # Start after the marker
        json_start = idx + len(marker)
        json_text = output[json_start:].strip()
        logger.error(
            f"[PARSE DEBUG] Found 'Final Answer:' at position {idx}. Text after marker (first 200 chars): {json_text[:200]}"
        )

        # Extract JSON using brace-matching state machine
        extracted = self._extract_json_with_state_machine(json_text)
        if not extracted:
            logger.error(
                f"[PARSE DEBUG] State machine failed to extract JSON. json_text length: {len(json_text)}, starts with: {json_text[:50]}"
            )
            return None

        logger.error(f"[PARSE DEBUG] Extracted JSON length: {len(extracted)} chars")
        logger.error(f"[PARSE DEBUG] First 150 chars: {extracted[:150]}")
        logger.error(f"[PARSE DEBUG] Last 150 chars: {extracted[-150:]}")

        try:
            parsed = json.loads(extracted)
            if isinstance(parsed, dict) and "census_data" in parsed:
                validated = AgentOutput(**parsed)  # Pydantic validation
                logger.info("Successfully extracted JSON after 'Final Answer:'")
                return validated.model_dump()
            else:
                logger.error(
                    f"[PARSE DEBUG] Parsed JSON but missing 'census_data' key. Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}"
                )
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                f"[PARSE DEBUG] JSON parse or Pydantic validation failed: {type(e).__name__}: {str(e)[:300]}"
            )
        return None

    def _extract_json_with_state_machine(self, text: str) -> Optional[str]:
        """
        Extract JSON object using state machine that handles:
        - Nested objects/arrays
        - Escaped quotes in strings
        - Braces inside string values
        - Square brackets in arrays
        """
        if not text:
            return None

        # Find first opening brace
        start_idx = text.find("{")
        if start_idx == -1:
            return None

        brace_count = 0
        bracket_count = 0  # Track array brackets too
        in_string = False
        escape_next = False

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            # Not in string, count braces and brackets
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    # Found matching closing brace
                    return text[start_idx : i + 1]
            elif char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1

        # If we got here, no complete JSON found
        logger.debug(
            f"State machine: Incomplete JSON (brace_count={brace_count}, bracket_count={bracket_count})"
        )
        return None
