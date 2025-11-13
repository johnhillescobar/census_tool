import json
import logging
import os
import sys
from typing import Dict, List

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.chroma_utils import (
    validate_and_fix_geo_params,
    validate_geography_hierarchy,
)

logger = logging.getLogger(__name__)


class GeographyValidationInput(BaseModel):
    """Input schema for geography validation tool."""

    dataset: str = Field(..., description="Census dataset path (e.g., 'acs/acs5')")
    year: int = Field(..., description="Census year (e.g., 2023)")
    geo_for: Dict[str, str] = Field(..., description="Geography for clause")
    geo_in: Dict[str, str] = Field(
        default_factory=dict, description="Geography in clause (optional)"
    )


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        """Validate geography parameters"""
        try:
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
            else:
                params = tool_input
        except json.JSONDecodeError as e:
            return json.dumps(
                {
                    "is_valid": False,
                    "errors": [f"Invalid JSON input: {e}"],
                    "warnings": [],
                }
            )

        try:
            validation_input = GeographyValidationInput(**params)
        except Exception as e:
            return json.dumps(
                {
                    "is_valid": False,
                    "errors": [f"Invalid parameters: {e}"],
                    "warnings": [],
                }
            )

        dataset = validation_input.dataset
        year = validation_input.year
        geo_for = validation_input.geo_for
        geo_in = validation_input.geo_in or {}

        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Attempt to normalize and fix parameters
            for_token, for_value, ordered_in = validate_and_fix_geo_params(
                dataset=dataset,
                year=year,
                geo_for=geo_for,
                geo_in=geo_in,
                validate_completeness=False,  # Don't raise on missing parents yet
            )

            # Check if ordering was changed
            original_in_tokens = list(geo_in.keys()) if geo_in else []
            repaired_in_tokens = [token for token, _ in ordered_in]

            if original_in_tokens and original_in_tokens != repaired_in_tokens:
                warnings.append(
                    f"Geography ordering auto-corrected from {original_in_tokens} to {repaired_in_tokens}"
                )

            # Check if for clause was simplified
            if len(geo_for) > 1:
                warnings.append(
                    f"Multiple geographies in 'for' clause simplified to target: {for_token}"
                )

            # Validate hierarchy completeness
            is_valid, missing, error_msg = validate_geography_hierarchy(
                dataset, year, for_token, repaired_in_tokens
            )

            if not is_valid:
                errors.append(error_msg)

            # Build repaired parameters
            repaired_for = {for_token: for_value}
            repaired_in = dict(ordered_in)

            result = {
                "is_valid": is_valid,
                "repaired_for": repaired_for,
                "repaired_in": repaired_in,
                "warnings": warnings,
                "errors": errors,
            }

            if is_valid:
                logger.info(
                    f"Geography validation passed for {dataset}/{year}/{for_token}"
                )
            else:
                logger.warning(f"Geography validation failed: {errors}")

            return json.dumps(result)

        except ValueError as e:
            # Validation error
            errors.append(str(e))
            return json.dumps(
                {
                    "is_valid": False,
                    "repaired_for": geo_for,
                    "repaired_in": geo_in,
                    "warnings": warnings,
                    "errors": errors,
                }
            )
        except Exception as e:
            # Unexpected error
            logger.error(f"Geography validation error: {e}")
            errors.append(f"Validation error: {e}")
            return json.dumps(
                {
                    "is_valid": False,
                    "repaired_for": geo_for,
                    "repaired_in": geo_in,
                    "warnings": warnings,
                    "errors": errors,
                }
            )


__all__ = ["GeographyValidationTool"]
