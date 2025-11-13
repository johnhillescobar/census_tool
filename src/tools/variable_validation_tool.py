import json
import logging
from typing import Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from src.utils.variable_validator import list_variables, validate_variables

logger = logging.getLogger(__name__)


class VariableValidationInput(BaseModel):
    action: str = Field(
        default="validate_variables",
        description="Operation to perform: validate_variables or list_variables",
    )
    dataset: str = Field(..., description="Dataset path such as acs/acs5")
    year: int = Field(..., description="Census year")
    variables: Optional[list[str]] = Field(
        default=None,
        description="Variables to validate (required for validate_variables)",
    )
    table_code: Optional[str] = Field(
        default=None,
        description="Optional table code prefix (e.g., B01003) when listing variables",
    )
    concept: Optional[str] = Field(
        default=None,
        description="Optional concept filter when listing variables",
    )
    limit: Optional[int] = Field(
        default=20, description="Maximum number of variables to return for list action"
    )


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        try:
            params = (
                json.loads(tool_input) if isinstance(tool_input, str) else tool_input
            )
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON input - {exc}"

        try:
            payload = VariableValidationInput(**params)
        except Exception as exc:
            logger.error("Variable validation input error: %s", exc)
            return f"Error: {exc}"

        if payload.action == "list_variables":
            try:
                result = list_variables(
                    dataset=payload.dataset,
                    year=payload.year,
                    table_code=payload.table_code,
                    concept=payload.concept,
                    limit=payload.limit or 20,
                )
            except Exception as exc:
                logger.error("list_variables failed: %s", exc)
                return f"Error: list_variables failed - {exc}"
            return json.dumps(result)

        if payload.variables is None:
            return "Error: 'variables' field is required for validate_variables action."

        try:
            result = validate_variables(
                dataset=payload.dataset,
                year=payload.year,
                variables=payload.variables,
            )
        except Exception as exc:
            logger.error("validate_variables failed: %s", exc)
            return f"Error: validate_variables failed - {exc}"

        return json.dumps(result)


__all__ = ["VariableValidationTool"]
