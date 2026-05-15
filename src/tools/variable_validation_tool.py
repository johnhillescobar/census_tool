import logging
import json
from typing import Any, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from src.domain.planning_tool_contracts import (
    VariableValidationRequest,
    VariableValidationResponse,
)
from src.services.variable_validator import list_variables, validate_variables
from src.tools.json_parse import parse_first_json

logger = logging.getLogger(__name__)


class VariableValidationTool(BaseTool):
    """
    Tool for validating Census API variables and discovering available alternatives.
    """

    name: str = "variable_validation"
    description: str = """
    Validate Census API variables for a specific dataset/year or list available variables.

    Input must be valid JSON with:
    - action: "validate_variables" (default) or "list_variables"
    - dataset: Dataset path like "acs/acs5" or "acs/acs5/subject"
    - year: Census year (e.g., 2023)
    - variables: Array of variable codes to validate (required for validate_variables)
    - table_code: Optional table prefix when listing variables
    - concept: Optional concept filter when listing variables
    - limit: Optional max count for list_variables (default 20)
    """

    args_schema: Type[BaseModel] = VariableValidationRequest

    def _parse_input(
        self, tool_input: str | dict[str, Any], tool_call_id: str | None
    ) -> str | dict[str, Any]:
        if isinstance(tool_input, str):
            try:
                parsed = parse_first_json(tool_input.strip())
            except json.JSONDecodeError:
                return tool_input
            if isinstance(parsed, dict):
                return parsed
        return tool_input

    def _error_response(
        self,
        request: VariableValidationRequest | None,
        error_code: str,
        error_message: str,
    ) -> VariableValidationResponse:
        action = request.action if request else "validate_variables"
        return VariableValidationResponse(
            success=False,
            request=request,
            action=action,
            warnings=[],
            error=error_code,
            error_message=error_message,
        )

    def _coerce_request(
        self,
        tool_input: VariableValidationRequest | str | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> VariableValidationRequest:
        if kwargs:
            if tool_input is None:
                tool_input = kwargs
            elif isinstance(tool_input, dict):
                tool_input = {**tool_input, **kwargs}
            elif isinstance(tool_input, VariableValidationRequest):
                tool_input = tool_input.model_copy(update=kwargs)

        if isinstance(tool_input, VariableValidationRequest):
            return tool_input
        if isinstance(tool_input, str):
            stripped = tool_input.strip()
            try:
                parsed = parse_first_json(stripped)
            except json.JSONDecodeError:
                return VariableValidationRequest.model_validate_json(stripped)
            return VariableValidationRequest.model_validate(parsed)
        return VariableValidationRequest.model_validate(tool_input)

    def _run(
        self,
        tool_input: VariableValidationRequest | str | dict[str, Any] | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> VariableValidationResponse:
        try:
            payload = self._coerce_request(tool_input, **kwargs)
        except ValidationError as exc:
            return self._error_response(
                request=None,
                error_code="INVALID_INPUT_SCHEMA",
                error_message=str(exc),
            )

        if payload.action == "list_variables":
            try:
                result = list_variables(
                    dataset=payload.dataset,
                    year=payload.year,
                    table_code=payload.table_code,
                    concept=payload.concept,
                    limit=payload.limit,
                )
            except Exception as exc:
                logger.error("list_variables failed: %s", exc)
                return self._error_response(
                    request=payload,
                    error_code="VARIABLE_LOOKUP_FAILED",
                    error_message=f"list_variables failed - {exc}",
                )
            return VariableValidationResponse(
                success=True,
                request=payload,
                action=payload.action,
                count=result["count"],
                variables=result["variables"],
            )

        try:
            result = validate_variables(
                dataset=payload.dataset,
                year=payload.year,
                variables=payload.variables,
            )
        except Exception as exc:
            logger.error("validate_variables failed: %s", exc)
            return self._error_response(
                request=payload,
                error_code="VARIABLE_LOOKUP_FAILED",
                error_message=f"validate_variables failed - {exc}",
            )

        return VariableValidationResponse(
            success=True,
            request=payload,
            action=payload.action,
            valid=result["valid"],
            invalid=result["invalid"],
            years_available=result["years_available"],
            details=result["details"],
            alternatives=result["alternatives"],
            source=result["source"],
            warnings=result["warnings"],
        )

    async def _arun(
        self,
        tool_input: VariableValidationRequest | str | dict[str, Any] | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> VariableValidationResponse:
        return self._run(tool_input, **kwargs)


__all__ = ["VariableValidationTool"]
