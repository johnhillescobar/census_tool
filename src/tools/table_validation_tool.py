import json
import logging
from typing import Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from src.utils.dataset_geography_validator import geography_supported
from src.utils.telemetry import record_event

logger = logging.getLogger(__name__)


class TableValidationInput(BaseModel):
    table_code: str = Field(..., description="Table code like B01003")
    geography_level: str = Field(..., description="Requested geography level")
    dataset: str = Field(default="acs/acs5", description="Dataset path")
    year: int = Field(default=2023, description="Census year")


class TableValidationTool(BaseTool):
    """
    Validate table supports requested geography
    """

    name: str = "validate_table_geography"
    description: str = """
    Check if a Census table supports a specific geography level.

    Input must be valid JSON:
    - table_code: Table code like "B01003" (required)
    - geography_level: Level like "county" (required)
    - dataset: Dataset like "acs/acs5" (optional, default acs/acs5)
    - year: Census year (optional, default 2023)

    Examples:
    - {"table_code": "B01003", "geography_level": "county"}
    - {"table_code": "S0101", "geography_level": "tract", "dataset": "acs/acs5/subject"}
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, tool_input: str) -> str:
        """Validate table supports geography level"""

        try:
            params = json.loads(tool_input) if isinstance(tool_input, str) else tool_input
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input - {e}"

        try:
            payload = TableValidationInput(**params)
        except Exception as exc:
            return f"Error: {exc}"

        logger.info(
            "Validating table geography: table=%s level=%s dataset=%s year=%s",
            payload.table_code,
            payload.geography_level,
            payload.dataset,
            payload.year,
        )

        result = geography_supported(
            dataset=payload.dataset,
            year=payload.year,
            geography_level=payload.geography_level,
        )
        result.update(
            {
                "table_code": payload.table_code,
            }
        )

        record_event(
            "table_validation",
            {
                "dataset": payload.dataset,
                "year": payload.year,
                "geography_level": payload.geography_level,
                "supported": result["supported"],
            },
        )

        return json.dumps(result)
