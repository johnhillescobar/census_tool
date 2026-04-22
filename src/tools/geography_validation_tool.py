import logging
from typing import Any, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from src.clients.chroma_utils import (
    validate_and_fix_geo_params,
    validate_geography_hierarchy,
)
from src.domain.planning_tool_contracts import (
    GeographyValidationRequest,
    GeographyValidationResponse,
)

logger = logging.getLogger(__name__)


class GeographyValidationTool(BaseTool):
    """
    Validate geography parameters before making Census API call.

    This tool checks geography hierarchy requirements and auto-corrects
    ordering issues, providing warnings and errors to help the agent
    construct valid API requests.
    """

    name: str = "validate_geography_params"
    description: str = """
    Validate geography parameters before making Census API call.
    
    Input must be valid JSON with:
    - dataset: Dataset path (e.g., "acs/acs5")
    - year: Census year (e.g., 2023)
    - geo_for: Geography for clause (e.g., {"county": "*"})
    - geo_in: Geography in clause (optional, e.g., {"state": "06"})
    
    Returns validation result with:
    - is_valid: bool - Whether parameters are valid
    - repaired_for: Corrected for clause
    - repaired_in: Corrected in clause (ordered properly)
    - warnings: List of corrections made
    - errors: List of validation errors
    
    Use this tool BEFORE calling census_api_call to ensure your geography
    parameters are correct and complete.
    """

    args_schema: Type[BaseModel] = GeographyValidationRequest

    def _error_response(
        self,
        request: GeographyValidationRequest | None,
        error_code: str,
        error_message: str,
    ) -> GeographyValidationResponse:
        return GeographyValidationResponse(
            success=False,
            request=request,
            is_valid=False,
            repaired_for=request.geo_for if request else {},
            repaired_in=request.geo_in if request else {},
            warnings=[],
            errors=[error_message],
            error=error_code,
            error_message=error_message,
        )

    def _coerce_request(
        self, tool_input: GeographyValidationRequest | str | dict[str, Any]
    ) -> GeographyValidationRequest:
        if isinstance(tool_input, GeographyValidationRequest):
            return tool_input
        if isinstance(tool_input, str):
            return GeographyValidationRequest.model_validate_json(tool_input)
        if isinstance(tool_input, dict) and tool_input.get("geo_in") is None:
            payload = dict(tool_input)
            payload.pop("geo_in", None)
            return GeographyValidationRequest.model_validate(payload)
        return GeographyValidationRequest.model_validate(tool_input)

    def _run(
        self,
        tool_input: GeographyValidationRequest | str | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> GeographyValidationResponse:
        """Validate geography parameters"""
        try:
            request_obj = self._coerce_request(tool_input)
        except ValidationError as exc:
            return self._error_response(
                request=None,
                error_code="INVALID_INPUT_SCHEMA",
                error_message=str(exc),
            )

        warnings: list[str] = []
        errors: list[str] = []

        try:
            # Attempt to normalize and fix parameters
            for_token, for_value, ordered_in = validate_and_fix_geo_params(
                dataset=request_obj.dataset,
                year=request_obj.year,
                geo_for=request_obj.geo_for,
                geo_in=request_obj.geo_in,
                validate_completeness=False,  # Don't raise on missing parents yet
            )

            # Check if ordering was changed
            original_in_tokens = (
                list(request_obj.geo_in.keys()) if request_obj.geo_in else []
            )
            repaired_in_tokens = [token for token, _ in ordered_in]

            if original_in_tokens and original_in_tokens != repaired_in_tokens:
                warnings.append(
                    f"Geography ordering auto-corrected from {original_in_tokens} to {repaired_in_tokens}"
                )

            # Check if for clause was simplified
            if len(request_obj.geo_for) > 1:
                warnings.append(
                    f"Multiple geographies in 'for' clause simplified to target: {for_token}"
                )

            # Validate hierarchy completeness
            is_valid, _missing, error_msg = validate_geography_hierarchy(
                request_obj.dataset, request_obj.year, for_token, repaired_in_tokens
            )

            if not is_valid:
                errors.append(error_msg)

            # Build repaired parameters
            repaired_for = {for_token: for_value}
            repaired_in = dict(ordered_in)

            if is_valid:
                logger.info(
                    "Geography validation passed for %s/%s/%s",
                    request_obj.dataset,
                    request_obj.year,
                    for_token,
                )
            else:
                logger.warning("Geography validation failed: %s", errors)

            return GeographyValidationResponse(
                success=True,
                request=request_obj,
                is_valid=is_valid,
                repaired_for=repaired_for,
                repaired_in=repaired_in,
                warnings=warnings,
                errors=errors,
            )

        except Exception as exc:
            logger.error("Geography validation error: %s", exc)
            return self._error_response(
                request=request_obj,
                error_code="VALIDATION_RUNTIME_ERROR",
                error_message=str(exc),
            )

    async def _arun(
        self,
        tool_input: GeographyValidationRequest | str | dict[str, Any],
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> GeographyValidationResponse:
        return self._run(tool_input)


__all__ = ["GeographyValidationTool"]
