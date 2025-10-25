import os
import sys
import logging
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any, List, Literal
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class ChartToolInput(BaseModel):
    """Input for chart creation"""

    chart_type: Literal["bar", "line"] = Field(
        ..., description="Chart type: 'bar' for comparisons, 'line' for trends"
    )
    x_column: str = Field(..., description="Column name for x-axis")
    y_column: str = Field(..., description="Column name for y-axis")
    title: str = Field(default="Census Data Visualization", description="Chart title")
    data: Dict[str, Any] = Field(
        ..., description="Census data dict from census_api_call tool"
    )


class ChartTool(BaseTool):
    """Create data visualizations (bar, line charts)"""

    name: str = "create_chart"
    description: str = """
    Create data visualizations from census data
    
    Input must be valid JSON with these fields:
    - chart_type: Chart type (bar, line)
    - x_column: Column name for x-axis
    - y_column: Column name for y-axis  
    - title: Chart title (optional, defaults to 'Census Data Visualization')
    - data: Census data dict from census_api_call tool
    """

    # args_schema = ChartToolInput  # Disabled for ReAct compatibility
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
        """Create a chart from the input data and save to data/charts/"""
        try:
            # Parse input
            if isinstance(tool_input, str):
                params = json.loads(tool_input)
            else:
                params = tool_input

            # Extract parameters (moved inside try block)
            chart_type = params.get("chart_type")
            x_column = params.get("x_column")
            y_column = params.get("y_column")
            title = params.get("title", "Census Data Visualization")
            data = params.get("data")

            # Validate required parameters
            if not all([chart_type, x_column, y_column, data]):
                return "Error: Missing required parameters (chart_type, x_column, y_column, data)"

            # Create DataFrame from census data
            df = self._create_dataframe_from_json(data)

            # Create chart based on type
            if chart_type == "bar":
                fig = px.bar(df, x=x_column, y=y_column, title=title)
            elif chart_type == "line":
                fig = px.line(df, x=x_column, y=y_column, title=title)
            else:
                return f"Error: Unsupported chart type: {chart_type}. Supported types: bar, line"

            # Ensure output directory exists
            charts_dir = Path("data/charts")
            charts_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chart_{chart_type}_{timestamp}.png"
            filepath = charts_dir / filename

            # Save chart to file
            try:
                fig.write_image(str(filepath), format="png", width=800, height=600)
                logger.info(f"Chart saved to {filepath}")
                return f"Chart created successfully: {filepath}"
            except Exception as save_error:
                logger.error(f"Error saving chart: {save_error}")
                # Fallback: try HTML format if PNG fails
                html_path = charts_dir / f"chart_{chart_type}_{timestamp}.html"
                fig.write_html(str(html_path))
                return f"Chart saved as HTML: {html_path}"

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input - {e}"
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return f"Error: {str(e)}"
