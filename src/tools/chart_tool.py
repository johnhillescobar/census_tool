import os
import sys
import logging
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Literal
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import plotly.express as px
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.dataframe_utils import _create_dataframe_from_json

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
            df = _create_dataframe_from_json(data)
            # Reset index to prevent Plotly from using index as values
            df = df.reset_index(drop=True)

            # Validate columns exist
            if x_column not in df.columns:
                error_msg = f"Error: x_column '{x_column}' not found in data. Available columns: {list(df.columns)}"
                logger.error(error_msg)
                return error_msg
            if y_column not in df.columns:
                error_msg = f"Error: y_column '{y_column}' not found in data. Available columns: {list(df.columns)}"
                logger.error(error_msg)
                return error_msg

            # Log actual data being plotted
            logger.info("=== Pre-Plot Validation ===")
            logger.info(f"Chart type: {chart_type}")
            logger.info(f"X column: '{x_column}' | Y column: '{y_column}'")
            logger.info(f"X data type: {df[x_column].dtype}")
            logger.info(f"Y data type: {df[y_column].dtype}")
            logger.info(f"X data sample (first 5): {df[x_column].head(5).tolist()}")
            logger.info(f"Y data sample (first 5): {df[y_column].head(5).tolist()}")

            # Check for numeric Y column
            if not pd.api.types.is_numeric_dtype(df[y_column]):
                logger.warning(
                    f"Y column '{y_column}' is not numeric! Attempting conversion..."
                )
                try:
                    df[y_column] = pd.to_numeric(df[y_column], errors="coerce")
                    logger.info(
                        f"Conversion successful. New dtype: {df[y_column].dtype}"
                    )
                except Exception as conv_error:
                    logger.error(f"Conversion failed: {conv_error}")

            # Log Y data statistics
            try:
                y_min = df[y_column].min()
                y_max = df[y_column].max()
                y_mean = df[y_column].mean()
                logger.info(f"Y data range: {y_min} to {y_max} (mean: {y_mean:.2f})")
            except Exception as stat_error:
                logger.warning(f"Could not compute Y statistics: {stat_error}")

            logger.info(f"DataFrame shape for plotting: {df.shape}")
            logger.info("=== End Pre-Plot Validation ===\n")

            # Set default color for charts. # Chosen as a deep blue for visual distinction.
            chart_color = "#111184"

            # Create chart based on type
            if chart_type == "bar":
                fig = px.bar(df, x=x_column, y=y_column, title=title)
                # Set color for all bars using marker_color
                fig.update_traces(marker_color=chart_color)
            elif chart_type == "line":
                fig = px.line(df, x=x_column, y=y_column, title=title)
                # Set color for line using line_color
                fig.update_traces(line_color=chart_color)
            else:
                return f"Error: Unsupported chart type: {chart_type}. Supported types: bar, line"

            # Rotate x-axis labels for better readability
            # -45 degrees makes labels diagonal and readable
            fig.update_xaxes(tickangle=-45)

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
