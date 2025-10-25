import os
import sys
import logging
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any, List, Literal
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class TableToolInput(BaseModel):
    """Input for table creation"""

    format: Literal["csv", "excel", "html"] = Field(
        default="csv",
        description="Output format: 'csv' for simple export, 'excel' for Excel files, 'html' for web tables",
    )
    filename: Optional[str] = Field(
        default=None, description="Optional custom filename (without extension)"
    )
    title: Optional[str] = Field(
        default="Census Data Table", description="Table title/description"
    )
    data: Dict[str, Any] = Field(
        ..., description="Census data dict from census_api_call tool"
    )


class TableTool(BaseTool):
    """Export census data as formatted tables (CSV, Excel, HTML)"""

    name: str = "create_table"
    description: str = """
    Export census data as formatted tables
    
    Input must be valid JSON with these fields:
    - format: Output format (csv, excel, html) - defaults to csv
    - filename: Optional custom filename (without extension)
    - title: Table title/description (optional)
    - data: Census data dict from census_api_call tool
    """

    # args_schema = TableToolInput  # Disabled for ReAct compatibility
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _create_dataframe_from_json(self, json_obj: Dict) -> pd.DataFrame:
        """
        Creates a pandas DataFrame from Census API response format.

        Handles nested structure from agent: {"data": {"success": True, "data": [...]}}
        Converts numeric columns from strings to proper numeric types.
        """
        if not isinstance(json_obj, dict):
            raise ValueError("Input must be a dictionary.")

        # Handle nested data structure from agent
        if (
            "data" in json_obj
            and isinstance(json_obj["data"], dict)
            and "data" in json_obj["data"]
        ):
            # Format: {"data": {"success": True, "data": [["headers"], ["rows"]]}}
            data = json_obj["data"]["data"]
        elif "data" in json_obj:
            # Format: {"data": [["headers"], ["rows"]]}
            data = json_obj["data"]
        else:
            raise KeyError("JSON object must contain a 'data' key.")

        if not isinstance(data, list) or len(data) < 2:
            raise ValueError(
                "The 'data' key must contain a list with at least a header row and one data row."
            )

        header = data[0]
        rows = data[1:]

        df = pd.DataFrame(rows, columns=header)

        # Convert numeric columns from strings to proper numeric types
        for col in df.columns:
            # Skip NAME column and other text columns
            if col.lower() in ["name", "geo_id", "state", "county"]:
                continue

            try:
                # Try to convert to numeric, coercing errors to NaN
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except (ValueError, TypeError):
                # If conversion fails, leave as string
                continue

        return df

    def _run(self, tool_input: str) -> str:
        """Create a table from the input data and save to data/tables/"""
        try:
            # Parse input
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
            else:
                params = tool_input

            # Extract parameters
            format_type = params.get("format", "csv")
            filename = params.get("filename")
            title = params.get("title", "Census Data Table")
            data = params.get("data")

            # Validate required parameters
            if not data:
                return "Error: Missing required parameter (data)"

            # Validate format
            if format_type not in ["csv", "excel", "html"]:
                return f"Error: Unsupported format: {format_type}. Supported formats: csv, excel, html"

            # Create DataFrame from census data
            df = self._create_dataframe_from_json(data)

            # Ensure output directory exists
            tables_dir = Path("data/tables")
            tables_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"table_{format_type}_{timestamp}"

            # Add appropriate extension
            if format_type == "csv":
                filepath = tables_dir / f"{filename}.csv"
            elif format_type == "excel":
                filepath = tables_dir / f"{filename}.xlsx"
            elif format_type == "html":
                filepath = tables_dir / f"{filename}.html"

            # Save table based on format
            try:
                if format_type == "csv":
                    df.to_csv(filepath, index=False, encoding="utf-8")
                elif format_type == "excel":
                    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name="Census Data", index=False)
                elif format_type == "html":
                    # Create HTML table with title
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>{title}</title>
                        <style>
                            table {{ border-collapse: collapse; width: 100%; }}
                            th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                            th {{ background-color: #f2f2f2; }}
                        </style>
                    </head>
                    <body>
                        <h1>{title}</h1>
                        {df.to_html(index=False, escape=False, table_id="census-table")}
                    </body>
                    </html>
                    """
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(html_content)

                logger.info(f"Table saved to {filepath}")
                return f"Table created successfully: {filepath}"

            except Exception as save_error:
                logger.error(f"Error saving table: {save_error}")
                return f"Error saving table: {str(save_error)}"

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input - {e}"
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            return f"Error: {str(e)}"
