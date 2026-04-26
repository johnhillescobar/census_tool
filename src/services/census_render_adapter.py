import logging

from src.domain.census_tool_contract import (
    StrictCensusApiResponse,
    StrictCensusApiRawTable,
)

logger = logging.getLogger(__name__)


# TODO: remove this function and replace it with a function that uses the StrictCensusApiResponse model. See T2-CG-010.
def response_to_tabular_payload(
    census_data: StrictCensusApiResponse,
) -> StrictCensusApiRawTable:
    rows = [
        [record.values.get(header, "") for header in census_data.headers]
        for record in census_data.records
    ]
    return StrictCensusApiRawTable(headers=census_data.headers, rows=rows)
