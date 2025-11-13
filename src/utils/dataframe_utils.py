import logging
import pandas as pd
from typing import Dict

logger = logging.getLogger(__name__)


def _create_dataframe_from_json(json_obj: Dict) -> pd.DataFrame:
    """
    Creates a pandas DataFrame from Census API response format.

    Handles nested structure from agent: {"data": {"success": True, "data": [...]}}
    Converts numeric columns from strings to proper numeric types.
    """
    logger.info("=== DataFrame Creation Debug ===")
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
        logger.info("Detected nested format: {'data': {'success': ..., 'data': [...]}}")
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
            col: (df[col].iloc[0], type(df[col].iloc[0]).__name__) for col in df.columns
        }
        logger.info(f"First row values with types: {first_row_sample}")

    # Convert numeric columns from strings to proper numeric types
    for col in df.columns:
        col_lower = col.lower()

        # Skip identifier/text columns using pattern matching
        # Match columns containing: name, geo, code (as identifiers), label, concept, variable
        # Also skip standard geography identifiers
        skip_patterns = [
            "name",  # Matches: NAME, Area Name, CSA Name, etc.
            "geo",  # Matches: GeoID, GEO_ID, geo_id, etc.
            "code",  # Matches: Code, CSA Code, etc. (but be careful - some codes are numeric)
            "label",  # Matches: Label
            "concept",  # Matches: Concept
            "variable",  # Matches: Variable
            "state",  # Matches: state, State (part)
            "county",  # Matches: county, County Name
        ]

        # Check if column name contains any skip pattern
        should_skip = any(pattern in col_lower for pattern in skip_patterns)

        # Special case: "Code" columns might be numeric identifiers (like CBSA codes)
        # Only skip if it's clearly a text identifier (e.g., "CSA Code" when there's also "CSA Name")
        if "code" in col_lower and not should_skip:
            # Check if there's a corresponding "Name" column that suggests this is an identifier
            # If Code column is the only identifier, it might be numeric
            has_name_column = any("name" in c.lower() for c in df.columns if c != col)
            if has_name_column:
                should_skip = True

        if should_skip:
            logger.info(f"Skipping column '{col}' (text/identifier column)")
            continue

        logger.info(f"Processing column '{col}' for numeric conversion...")
        logger.info(f"  Sample values: {df[col].head(3).tolist()}")

        try:
            cleaned = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
                .str.strip()
            )
            # Try to convert to numeric, coercing errors to NaN
            original_dtype = df[col].dtype
            df[col] = pd.to_numeric(cleaned, errors="coerce")
            logger.info(f"  Converted '{col}': {original_dtype} -> {df[col].dtype}")
            logger.info(f"  Post-conversion values: {df[col].head(3).tolist()}")
            logger.info(f"  NaN count: {df[col].isna().sum()}")

            # If conversion produced all NaNs, it was likely a text column
            # Revert to original string values
            if df[col].isna().all():
                logger.warning(
                    "Conversion produced all NaNs for column '%s'; reverting to string type. Original sample: %s",
                    col,
                    cleaned.head(3).tolist() if len(df) > 0 else [],
                )
                # Revert to original string values
                df[col] = cleaned
        except (ValueError, TypeError) as e:
            # If conversion fails, leave as string
            logger.warning(f"  FAILED to convert column '{col}': {e}")
            continue

    # Reorder columns: geography identifiers first, then value columns
    geography_cols = []
    value_cols = []

    for col in df.columns:
        col_lower = col.lower()
        # Use same patterns as type conversion skip list
        is_geography = any(
            pattern in col_lower
            for pattern in [
                "name",
                "geo",
                "code",
                "label",
                "concept",
                "variable",
                "state",
                "county",
                "place",
                "tract",
            ]
        )

        # Special case: "Code" columns - treat as geography if there's a corresponding "Name" column
        if "code" in col_lower:
            has_name_column = any("name" in c.lower() for c in df.columns if c != col)
            if has_name_column:
                is_geography = True

        if is_geography:
            geography_cols.append(col)
        else:
            value_cols.append(col)

    # Reorder: geography first, then values
    df = df[geography_cols + value_cols]

    logger.info(f"Final DataFrame dtypes: {df.dtypes.to_dict()}")
    logger.info(f"Sample data (first 3 rows):\n{df.head(3)}")
    logger.info("=== End DataFrame Creation Debug ===\n")

    return df
