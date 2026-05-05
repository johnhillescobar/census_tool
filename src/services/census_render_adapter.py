import pandas as pd
import logging
from pathlib import Path

from src.domain.census_tool_contract import (
    StrictCensusApiResponse,
    StrictCensusApiRawTable,
)
from src.services.dataframe_utils import (
    _create_dataframe_from_list_of_lists,
    _process_geography_columns,
)

logger = logging.getLogger(__name__)


def response_to_tabular_payload(
    census_data: StrictCensusApiResponse,
) -> StrictCensusApiRawTable:
    rows = [
        [record.values.get(header, "") for header in census_data.headers]
        for record in census_data.records
    ]
    return StrictCensusApiRawTable(headers=census_data.headers, rows=rows)


def response_to_dataframe(
    raw_table: StrictCensusApiRawTable, reset_index: bool = False
) -> pd.DataFrame:
    logger.info(f"Converting raw table to dataframe: {raw_table.headers}")

    if not isinstance(raw_table.rows, list):
        raise ValueError("raw_table.rows must be a list")

    df_initial = _create_dataframe_from_list_of_lists(raw_table.rows, raw_table.headers)

    df = _process_geography_columns(df_initial)

    if reset_index:
        df = df.reset_index(drop=True)

    return df


def _ensure_export_parent_dir(filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)


def export_dataframe_to_csv(df: pd.DataFrame, filepath: Path) -> None:
    _ensure_export_parent_dir(filepath)
    df.to_csv(filepath, index=False, encoding="utf-8")


def export_dataframe_to_parquet(df: pd.DataFrame, filepath: Path) -> None:
    _ensure_export_parent_dir(filepath)
    df.to_parquet(filepath, index=False)
