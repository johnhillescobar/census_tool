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
        logger.info("=== ChartTool Data Extraction Debug ===")
        logger.info(f"Input json_obj type: {type(json_obj)}")
        logger.info(
            f"Input json_obj keys: {list(json_obj.keys()) if isinstance(json_obj, dict) else 'N/A'}"
        )

        if not isinstance(json_obj, dict):
            raise ValueError("Input must be a dictionary.")

        # Handle nested data structure from agent
        if (
            "data" in json_obj
            and isinstance(json_obj["data"], dict)
            and "data" in json_obj["data"]
        ):
            # Format: {"data": {"success": True, "data": [["headers"], ["rows"]]}}
            logger.info(
                "Detected nested format: {'data': {'success': ..., 'data': [...]}}"
            )
            data = json_obj["data"]["data"]
        elif "data" in json_obj:
            # Format: {"data": [["headers"], ["rows"]]}
            logger.info("Detected simple format: {'data': [...]}")
            data = json_obj["data"]
        else:
            raise KeyError("JSON object must contain a 'data' key.")

        logger.info(f"Extracted data type: {type(data)}")
        logger.info(
            f"Extracted data length: {len(data) if isinstance(data, list) else 'N/A'}"
        )

        if not isinstance(data, list) or len(data) < 2:
            raise ValueError(
                "The 'data' key must contain a list with at least a header row and one data row."
            )

        header = data[0]
        rows = data[1:]

        logger.info(f"Headers: {header}")
        logger.info(f"First data row: {rows[0] if rows else 'No data'}")
        logger.info(f"Number of data rows: {len(rows)}")

        df = pd.DataFrame(rows, columns=header)

        logger.info(
            f"DataFrame created with shape: {df.shape}, columns: {list(df.columns)}"
        )
        logger.info(f"DataFrame dtypes BEFORE conversion: {df.dtypes.to_dict()}")

        # Log first row values and their types
        if len(df) > 0:
            first_row_sample = {
                col: (df[col].iloc[0], type(df[col].iloc[0]).__name__)
                for col in df.columns
            }
            logger.info(f"First row values with types: {first_row_sample}")

        # Convert numeric columns from strings to proper numeric types
        for col in df.columns:
            # Skip only truly non-numeric text columns
            if col.lower() in ["name", "geo_id"]:
                logger.info(f"Skipping column '{col}' (text column)")
                continue

            logger.info(f"Processing column '{col}' for numeric conversion...")
            logger.info(f"  Sample values: {df[col].head(3).tolist()}")

            try:
                # Remove commas from strings before conversion (Census API returns "1,234,567")
                original_dtype = df[col].dtype
                df[col] = df[col].astype(str).str.replace(",", "", regex=False)
                df[col] = pd.to_numeric(df[col], errors="coerce")
                logger.info(f"  Converted '{col}': {original_dtype} -> {df[col].dtype}")
                logger.info(f"  Post-conversion values: {df[col].head(3).tolist()}")
                logger.info(f"  NaN count: {df[col].isna().sum()}")
            except (ValueError, TypeError) as e:
                # If conversion fails, leave as string
                logger.warning(f"  FAILED to convert column '{col}': {e}")
                continue

        logger.info(f"Final DataFrame dtypes: {df.dtypes.to_dict()}")
        logger.info(f"Sample data (first 3 rows):\n{df.head(3)}")

        # Reset index to prevent Plotly from using index as values
        df = df.reset_index(drop=True)
        logger.info(
            f"DataFrame index reset. Index range: {df.index.min()} to {df.index.max()}"
        )
        logger.info("=== End Data Extraction Debug ===\n")

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
