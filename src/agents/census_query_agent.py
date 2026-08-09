import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from src.agents.runtime.factory import build_agent_backend, resolve_agent_runtime
from src.domain.agent_clarification_context import AgentClarificationContext
from src.domain.agent_output_contract import (
    AgentPlanOutput,
    agent_output_to_legacy_dict,
    validate_comparison_rows_for_plan,
)
from src.domain.agent_plan_context import AgentPlanContext
from src.domain.census_tool_contract import StrictCensusApiResponse
from src.llm.config import LLM_CONFIG
from src.llm.factory import create_llm
from src.llm.prompts.clarification_writer import build_clarification_writer_prompt
from src.llm.prompts.execution_agent import build_execution_agent_prompt
from src.llm.prompts.planning_agent import build_planning_agent_prompt
from src.services.agent_clarification_copy import (
    build_agent_clarification_copy,
    format_clarification_options_for_writer,
)
from src.services.agent_plan_context import format_clarification_directives, format_plan_directives
from src.tools.area_resolution_tool import AreaResolutionTool
from src.tools.census_api_tool import CensusAPITool
from src.tools.chart_tool import ChartTool
from src.tools.geography_discovery_tool import GeographyDiscoveryTool
from src.tools.geography_hierarchy_tool import GeographyHierarchyTool
from src.tools.geography_validation_tool import GeographyValidationTool
from src.tools.pattern_builder_tool import PatternBuilderTool
from src.tools.propose_grounded_plan_tool import ProposeGroundedPlanTool
from src.tools.select_clarification_option_tool import SelectClarificationOptionTool
from src.tools.strict_census_api_tool import StrictCensusApiTool
from src.tools.table_catalog_retrieval_tool import TableCatalogRetrievalTool
from src.tools.table_search_tool import TableSearchTool
from src.tools.table_tool import TableTool
from src.tools.variable_validation_tool import VariableValidationTool

load_dotenv()

logger = logging.getLogger(__name__)


COMPARISON_INPUT_ROW_FIELDS = frozenset({"year", "geo_id", "metric", "value", "benchmark_value"})
CENSUS_DATA_FIELDS = frozenset({"success", "data", "variables", "url"})
STRICT_CENSUS_TOOL_NAME = "strict_census_api_call"
PLANNING_EXCLUDED_TOOL_NAMES = frozenset(
    {
        "census_api_call",
        STRICT_CENSUS_TOOL_NAME,
        "create_chart",
    }
)


class AgentOutput(AgentPlanOutput):
    """Backward-compatible alias for the typed agent output contract."""


class CensusQueryAgent:
    """
    Reasoning agent for Census queries.
    Uses the modern create_agent runtime with Census tools.
    """

    def __init__(
        self,
        allow_offline: bool = True,
        mode: str = "execution",
    ):
        if mode not in {"execution", "planning"}:
            raise ValueError(f"unsupported agent mode: {mode}")
        self.mode = mode
        self.offline_mode = False
        self._active_plan_context: AgentPlanContext | None = None
        self._select_clarification_tool = SelectClarificationOptionTool()
        self.runtime = resolve_agent_runtime()

        missing_api_key = not os.getenv("OPENAI_API_KEY")
        if allow_offline and missing_api_key:
            self.offline_mode = True
            logger.warning(
                "OPENAI_API_KEY not set. Initializing CensusQueryAgent in offline mode. "
                "Agent execution will be disabled; only parsing helpers are available."
            )
            self.llm = None
            self.tools = []
            self.backend = None
            return

        self.llm = create_llm(temperature=LLM_CONFIG["temperature"])

        all_tools = [
            GeographyDiscoveryTool(),
            GeographyValidationTool(),
            TableSearchTool(),
            TableCatalogRetrievalTool(),
            ProposeGroundedPlanTool(),
            CensusAPITool(),
            StrictCensusApiTool(),
            TableTool(),
            PatternBuilderTool(),
            AreaResolutionTool(),
            ChartTool(),
            GeographyHierarchyTool(),
            VariableValidationTool(),
        ]
        if self.mode == "planning":
            self.tools = [
                *[
                    tool
                    for tool in all_tools
                    if tool.name not in PLANNING_EXCLUDED_TOOL_NAMES
                ],
                self._select_clarification_tool,
            ]
        else:
            self.tools = all_tools
        system_prompt = self._build_modern_system_prompt()

        self.backend = build_agent_backend(
            llm=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
        )

    def _build_modern_system_prompt(self) -> str:
        if self.mode == "planning":
            return build_planning_agent_prompt(tool.name for tool in self.tools)
        return build_execution_agent_prompt(tool.name for tool in self.tools)

    def _build_executor_input(
        self,
        user_query: str,
        intent: dict,
        plan_context: AgentPlanContext | None,
        clarification_context: AgentClarificationContext | None = None,
    ) -> str:
        sections = []
        if clarification_context is not None:
            sections.extend(
                [
                    "Clarification resume context (MUST ground selection in these options):",
                    format_clarification_directives(clarification_context),
                    "",
                ]
            )
        if plan_context is not None:
            sections.extend(
                [
                    "Planning artifacts (MUST follow these constraints):",
                    format_plan_directives(plan_context),
                    "",
                ]
            )
        sections.extend(
            [
                f"User query: {user_query}",
                f"Intent: {intent}",
            ]
        )
        return "\n".join(sections)

    def solve(
        self,
        user_query: str,
        intent: dict,
        plan_context: AgentPlanContext | None = None,
        clarification_context: AgentClarificationContext | None = None,
    ) -> dict:
        """
        Reason through the query and return structured data
        """
        if self.mode == "planning":
            return self._solve_planning(user_query, intent, plan_context, clarification_context)

        if self.offline_mode:
            logger.warning("CensusQueryAgent.solve called in offline mode without API credentials.")
            return {
                "census_data": {"success": False, "data": []},
                "data_summary": "Agent execution skipped (no API credentials available)",
                "reasoning_trace": "Agent skipped because OPENAI_API_KEY is not configured",
                "answer_text": "Unable to complete this request because the CensusQueryAgent is running without LLM credentials. Provide OPENAI_API_KEY to enable agent execution.",
                "charts_needed": [],
                "tables_needed": [],
                "footnotes": [
                    "Agent execution disabled due to missing OPENAI_API_KEY.",
                    "Set OPENAI_API_KEY before running automated workflows or tests.",
                ],
                "comparison_input_rows": [],
            }

        if self.backend is None:
            raise RuntimeError("Agent backend is not initialized. Set OPENAI_API_KEY or enable offline mode.")

        self._active_plan_context = plan_context
        execution = self.backend.invoke(
            self._build_executor_input(
                user_query=user_query,
                intent=intent,
                plan_context=plan_context,
                clarification_context=clarification_context,
            )
        )
        result = {
            "output": execution.output,
            "intermediate_steps": execution.intermediate_steps,
        }

        return self._parse_solution(result)

    def _solve_planning(
        self,
        user_query: str,
        intent: dict,
        plan_context: AgentPlanContext | None = None,
        clarification_context: AgentClarificationContext | None = None,
    ) -> dict[str, Any]:
        if self.offline_mode:
            trace = (
                "Agent clarification skipped because OPENAI_API_KEY is not configured"
                if clarification_context is not None
                else "Agent planning skipped because OPENAI_API_KEY is not configured"
            )
            summary = "Clarification turn offline" if clarification_context is not None else "Planning turn offline"
            answer = (
                "Clarification turn skipped (no LLM credentials)."
                if clarification_context is not None
                else "Planning turn skipped (no LLM credentials)."
            )
            return {
                "reasoning_trace": trace,
                "data_summary": summary,
                "answer_text": answer,
            }

        if self.backend is None:
            raise RuntimeError("Agent backend is not initialized. Set OPENAI_API_KEY or enable offline mode.")

        self._active_plan_context = plan_context
        self._select_clarification_tool.bind_context(clarification_context)
        execution = self.backend.invoke(
            self._build_executor_input(
                user_query=user_query,
                intent=intent,
                plan_context=plan_context,
                clarification_context=clarification_context,
            )
        )
        intermediate_steps = execution.intermediate_steps or []
        output = (execution.output or "").strip()
        tool_names = [getattr(step[0], "tool", None) for step in intermediate_steps if step and len(step) >= 1]
        return {
            "reasoning_trace": f"Planning tool steps: {len(intermediate_steps)} ({', '.join(name for name in tool_names if name)})",
            "data_summary": output[:1000] if output else "Planning turn completed without text output.",
            "answer_text": output or "Planning turn completed.",
            "intermediate_steps": intermediate_steps,
        }

    def compose_clarification_prompt(self, clarification_context: AgentClarificationContext) -> dict[str, Any]:
        """Generate turn-1 clarification copy with readable labels and recommended default."""
        fallback = build_agent_clarification_copy(clarification_context)
        if self.offline_mode or self.llm is None:
            return {
                "answer_text": fallback,
                "reasoning_trace": "Clarification copy: deterministic fallback (agent offline)",
            }

        prompt = build_clarification_writer_prompt(
            user_question=clarification_context.original_query,
            clarification_needed=f"{clarification_context.requested_slot} ({clarification_context.reason_code})",
            available_options=format_clarification_options_for_writer(clarification_context),
        )
        response = self.llm.invoke(prompt)
        content = getattr(response, "content", None)
        if isinstance(content, str) and content.strip():
            return {
                "answer_text": content.strip(),
                "reasoning_trace": "Clarification copy: agent clarification_writer prompt",
            }
        return {
            "answer_text": fallback,
            "reasoning_trace": "Clarification copy: deterministic fallback (empty agent response)",
        }

    def _coerce_strict_census_response(self, observation: Any) -> StrictCensusApiResponse | None:
        if isinstance(observation, StrictCensusApiResponse):
            return observation
        if isinstance(observation, dict):
            try:
                return StrictCensusApiResponse.model_validate(observation)
            except ValidationError:
                return None
        if isinstance(observation, str):
            text = observation.strip()
            if not text.startswith("{"):
                return None
            try:
                return StrictCensusApiResponse.model_validate_json(text)
            except ValidationError:
                return None
        return None

    def _resolve_authoritative_strict_census_response(self, result: dict[str, Any] | None) -> StrictCensusApiResponse | None:
        if not result:
            return None
        for step in reversed(result.get("intermediate_steps", []) or []):
            if not step or len(step) < 2:
                continue
            action, observation = step[0], step[1]
            if getattr(action, "tool", None) != STRICT_CENSUS_TOOL_NAME:
                continue
            response = self._coerce_strict_census_response(observation)
            if response is not None and response.success:
                return response
        return None

    def _validate_agent_output_model(self, parsed: dict[str, Any], result: dict[str, Any] | None = None) -> AgentPlanOutput:
        authoritative_response = self._resolve_authoritative_strict_census_response(result)
        if authoritative_response is not None:
            parsed["census_data"] = authoritative_response
        validated = AgentPlanOutput(**parsed)
        if (
            self._active_plan_context is not None
            and self._active_plan_context.has_comparison_plan
            and self._active_plan_context.comparison is not None
            and validated.comparison_input_rows
        ):
            validate_comparison_rows_for_plan(
                validated.comparison_input_rows,
                self._active_plan_context.comparison,
            )
        return validated

    def _validate_agent_output(self, parsed: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
        return agent_output_to_legacy_dict(self._validate_agent_output_model(parsed, result))

    def _has_invalid_geography(self, result: dict, parsed: dict) -> bool:
        """Check if agent tried to query invalid geography"""
        intermediate_steps = result.get("intermediate_steps", [])

        for step in intermediate_steps:
            if not step or len(step) < 2:
                continue
            action, observation = step[0], step[1]

            if not action or not observation:
                continue

            # Check if resolve_area_name failed
            if hasattr(action, "tool") and action.tool == "resolve_area_name":
                if isinstance(observation, str) and observation.strip():
                    # If observation doesn't start with '{', it's likely an error message, not JSON
                    if not observation.strip().startswith("{"):
                        logger.info(f"Detected failed geography resolution: {observation[:100]}")
                        return True

            # Check if census_api_call returned success: False
            if hasattr(action, "tool") and action.tool == "census_api_call":
                try:
                    obs_dict = json.loads(observation) if isinstance(observation, str) else observation
                    if isinstance(obs_dict, dict) and obs_dict.get("success") is False:
                        logger.info(f"Detected failed Census API call: {obs_dict.get('error', 'Unknown error')}")
                        return True
                except (json.JSONDecodeError, TypeError, AttributeError):
                    # If observation isn't JSON, might be an error message
                    if isinstance(observation, str) and "error" in observation.lower():
                        return True
                    pass

        return False

    def _build_invalid_geography_response(self, result: dict, parsed: dict) -> dict:
        """Build error response for invalid geography"""
        return {
            "census_data": {"success": False, "data": []},
            "data_summary": "Invalid geography - not available in Census data",
            "reasoning_trace": "Geography resolution failed or Census API returned error",
            "answer_text": "I was unable to complete this query. The geography you requested is not available in the U.S. Census data. Please try a valid U.S. geography (state, county, city, etc.).",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [
                "The requested geography is not available in Census datasets.",
                "U.S. Census covers U.S. geographies only.",
            ],
            "comparison_input_rows": [],
        }

    def _is_clarification_answer(self, answer_text: str) -> bool:
        text = (answer_text or "").strip().lower()
        if not text:
            return False
        if text.endswith("?"):
            return True
        clarification_markers = (
            "which geography",
            "what geography",
            "please specify",
            "please choose",
            "please confirm",
        )
        return any(marker in text for marker in clarification_markers)

    def _normalize_error_response(self, parsed: dict, result: dict) -> dict:
        """
        Normalize invalid-geography failures only.
        Preserve clarification questions and other non-geography failures.
        """
        census_data = parsed.get("census_data", {})
        if isinstance(census_data, dict) and census_data.get("success") is False:
            answer_text = parsed.get("answer_text", "")
            if self._is_clarification_answer(answer_text):
                return parsed

            if self._has_invalid_geography(result, parsed):
                logger.info("Normalizing invalid geography response")
                parsed["answer_text"] = (
                    "I was unable to complete this query. "
                    "The geography you requested is not available in the U.S. Census data. "
                    "Please try a valid U.S. geography (state, county, city, etc.)."
                )
                if not isinstance(census_data, dict):
                    parsed["census_data"] = {"success": False, "data": []}
                elif "data" not in census_data:
                    parsed["census_data"]["data"] = []

        return parsed

    def _parse_solution(self, result: dict) -> dict:
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
            # Validate that geography resolution succeeded
            if self._has_invalid_geography(result, parsed):
                return self._build_invalid_geography_response(result, parsed)
            parsed = self._normalize_error_response(parsed, result)
            return self._validate_agent_output(parsed, result)

        parsed = self._extract_after_final_answer(output)
        if parsed:
            if self._has_invalid_geography(result, parsed):
                return self._build_invalid_geography_response(result, parsed)
            parsed = self._normalize_error_response(parsed, result)
            return self._validate_agent_output(parsed, result)

        if self._is_valid_json_without_prefix(output):
            logger.warning("Agent returned bare JSON without 'Final Answer:' prefix, attempting direct parse")
            parsed = self._try_direct_json_parse(output)
            if parsed:
                if self._has_invalid_geography(result, parsed):
                    return self._build_invalid_geography_response(result, parsed)
                parsed = self._normalize_error_response(parsed, result)
                return self._validate_agent_output(parsed, result)

        logger.warning("All parsing methods failed")
        logger.debug(f"Raw output sample: {output[:500]}")

        intermediate_steps = result.get("intermediate_steps", [])
        return {
            "census_data": {"success": False, "data": []},
            "data_summary": "Parsing failed - see logs",
            "reasoning_trace": f"Steps: {len(intermediate_steps)}",
            "answer_text": "Agent execution completed but output parsing failed",
            "charts_needed": [],
            "tables_needed": [],
            "footnotes": [],
            "comparison_input_rows": [],
        }

    def _try_direct_json_parse(self, output: str) -> dict | None:
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
                parsed = self._normalize_parsed_output_contract(parsed)
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
            logger.error(f"[PARSE DEBUG] Direct parse Pydantic ValidationError: {str(e)[:500]}")
        except Exception as e:
            logger.error(f"[PARSE DEBUG] Direct parse unexpected error: {type(e).__name__}: {str(e)[:300]}")
        return None

    def _build_empty_output_response(self, result: dict) -> dict[str, Any]:
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

        summary_parts = [f"The agent completed {step_count} tool steps but did not emit a final answer payload."]
        if last_tool:
            summary_parts.append(f"Last tool invoked: {last_tool}.")
        if last_observation:
            summary_parts.append("Review the session log for the final tool output.")

        data_summary = " ".join(summary_parts)
        answer_text = (
            "I gathered intermediate results but the response formatter did not run. "
            "Please rerun the question and I will try again."
        )

        census_data_payload: dict[str, Any] = {
            "success": False,
            "error": "empty_output",
        }
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
            "comparison_input_rows": [],
        }

    def _did_reach_iteration_limit(self, result: dict, output: str) -> bool:
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

    def _build_iteration_limit_response(self, result: dict, output: str) -> dict[str, Any]:
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

        summary_parts = [f"Stopped after {step_count} steps because the agent hit its iteration limit."]
        if last_tool:
            summary_parts.append(f"Last tool invoked: {last_tool}.")
        if last_observation:
            summary_parts.append("Review the session log for the final tool output.")

        data_summary = " ".join(summary_parts)
        answer_text = (
            "I gathered data but reached the reasoning step limit before formatting the final answer. "
            "Please rerun the question or adjust it and I will try again."
        )

        census_data_payload: dict[str, Any] = {
            "success": False,
            "error": "iteration_limit",
        }
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
            "comparison_input_rows": [],
        }

    def _coerce_observation_to_dict(self, observation: Any) -> dict[str, Any] | None:
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

    def _extract_after_final_answer(self, output: str) -> dict | None:
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
                parsed = self._normalize_parsed_output_contract(parsed)
                validated = AgentOutput(**parsed)  # Pydantic validation
                logger.info("Successfully extracted JSON after 'Final Answer:'")
                return validated.model_dump()
            else:
                logger.error(
                    f"[PARSE DEBUG] Parsed JSON but missing 'census_data' key. Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}"
                )
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"[PARSE DEBUG] JSON parse or Pydantic validation failed: {type(e).__name__}: {str(e)[:300]}")
        return None

    def _normalize_parsed_output_contract(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize common LLM contract drift before strict Pydantic validation.

        Current fix:
        - census_data.variables may arrive as a list (["NAME", "B01003_001E"]).
          Convert it to dict shape expected by CensusData:
          {"NAME": "NAME", "B01003_001E": "B01003_001E"}.
        - census_data may include API metadata (dataset, year, geo_for, geo_in).
          Strip to the canonical payload fields and synthesize url when possible.
        """
        census_data = parsed.get("census_data")
        if not isinstance(census_data, dict):
            return parsed

        variables = census_data.get("variables")
        if isinstance(variables, list):
            normalized_variables: dict[str, str] = {}
            for item in variables:
                if isinstance(item, str) and item.strip():
                    normalized_variables[item] = item
            census_data["variables"] = normalized_variables

            logger.warning("Normalized census_data.variables from list to dict for contract compatibility")

        stripped_census_data = {key: census_data[key] for key in CENSUS_DATA_FIELDS if key in census_data}
        if "success" not in stripped_census_data:
            stripped_census_data["success"] = census_data.get("success", False)
        if "data" not in stripped_census_data:
            stripped_census_data["data"] = census_data.get("data", [])
        if "url" not in stripped_census_data and census_data.get("year") is not None and census_data.get("dataset"):
            stripped_census_data["url"] = f"https://api.census.gov/data/{census_data['year']}/{census_data['dataset']}"
        if stripped_census_data != census_data:
            logger.warning("Normalized census_data by stripping extra agent/API metadata fields")
            parsed["census_data"] = stripped_census_data
            census_data = stripped_census_data

        if "comparison_input_rows" not in parsed:
            parsed["comparison_input_rows"] = []
        else:
            normalized_rows: list[dict[str, Any]] = []
            for row in parsed["comparison_input_rows"]:
                if not isinstance(row, dict):
                    continue
                normalized_row = {key: row[key] for key in COMPARISON_INPUT_ROW_FIELDS if key in row}
                if normalized_row:
                    normalized_rows.append(normalized_row)
            if normalized_rows != parsed["comparison_input_rows"]:
                logger.warning("Normalized comparison_input_rows by stripping extra agent fields")
            parsed["comparison_input_rows"] = normalized_rows

        return parsed

    def _extract_json_with_state_machine(self, text: str) -> str | None:
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
        logger.debug(f"State machine: Incomplete JSON (brace_count={brace_count}, bracket_count={bracket_count})")
        return None

    def _is_valid_json_without_prefix(self, output: str) -> bool:
        """
        Check if output is valid JSON but missing the 'Final Answer:' prefix.
        This handles cases where the agent returns tool output directly.
        """
        if not output or "Final Answer:" in output:
            return False

        # Check if it starts with a JSON object
        stripped = output.strip()
        if not stripped.startswith("{"):
            return False

        # Try to parse as JSON
        try:
            parsed = json.loads(stripped)
            # Check if it has the expected structure
            if isinstance(parsed, dict) and "census_data" in parsed:
                logger.info("Detected bare JSON output without 'Final Answer:' prefix")
                return True
        except json.JSONDecodeError:
            pass

        return False
