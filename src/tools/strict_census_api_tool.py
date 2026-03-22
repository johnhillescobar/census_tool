import logging
from typing import Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from src.clients.census_api_utils import build_geo_filters, fetch_census_data
from src.clients.telemetry import record_event
from src.domain.census_tool_contract import (
    StrictCensusApiErrorCode,
    StrictCensusApiRawTable,
    StrictCensusApiRecord,
    StrictCensusApiRequest,
    StrictCensusApiResponse,
)

logger = logging.getLogger(__name__)


class StrictCensusApiTool(BaseTool):
    name: str = "strict_census_api_call"
    description: str = (
        "Execute a strict typed Census API query. "
        "Input must follow strict request contract with year, dataset, variables, "
        "geo_for, optional geo_in, and optional geo_in_chained."
    )
    args_schema: Type[BaseModel] = StrictCensusApiRequest

    def _error_response(
        self,
        request: StrictCensusApiRequest | None,
        error_code: StrictCensusApiErrorCode,
        error_message: str,
    ) -> StrictCensusApiResponse:
        payload = StrictCensusApiResponse(
            success=False,
            request=request,
            headers=[],
            records=[],
            row_count=0,
            error=error_code,
            error_message=error_message,
        )

        record_event(
            "strict_census_api_call",
            {
                "dataset": request.dataset if request is not None else None,
                "year": request.year if request is not None else None,
                "variables": request.variables if request is not None else None,
                "success": False,
                "error": error_code,
                "error_message": error_message,
            },
        )
        return payload

    def _run(
        self,
        tool_input: StrictCensusApiRequest,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> StrictCensusApiResponse:
        request_obj: StrictCensusApiRequest | None = None

        # 1) Validate request through strict typed contract only
        try:
            request_obj = StrictCensusApiRequest.model_validate(tool_input)
        except ValidationError as exc:
            return self._error_response(
                request=None,
                error_code="INVALID_INPUT_SCHEMA",
                error_message=str(exc),
            )

        # 2) Build geo filters with strict hierarchy validation
        try:
            geo_filters = build_geo_filters(
                dataset=request_obj.dataset,
                year=request_obj.year,
                geo_for=request_obj.geo_for,
                geo_in=request_obj.geo_in,
                geo_in_chained=request_obj.geo_in_chained,
            )
        except Exception as exc:
            return self._error_response(
                request=request_obj,
                error_code="INVALID_GEO_PARAMS",
                error_message=str(exc),
            )

        # 3) Execute API call
        result = fetch_census_data(
            dataset=request_obj.dataset,
            year=request_obj.year,
            variables=request_obj.variables,
            geo={"filters": geo_filters},
        )

        if not result.get("success"):
            return self._error_response(
                request=request_obj,
                error_code="API_HTTP_ERROR",
                error_message=str(result.get("error", "Unknown API error")),
            )

        # 4) Validate payload shape
        raw_payload = result.get("data")
        if not isinstance(raw_payload, list) or len(raw_payload) == 0:
            return self._error_response(
                request=request_obj,
                error_code="API_PAYLOAD_SHAPE_INVALID",
                error_message="Expected non-empty list-of-lists payload from Census API",
            )

        try:
            raw_table = StrictCensusApiRawTable(
                headers=[str(value) for value in raw_payload[0]],
                rows=[[str(value) for value in row] for row in raw_payload[1:]],
            )
        except ValidationError as exc:
            return self._error_response(
                request=request_obj,
                error_code="API_PAYLOAD_SHAPE_INVALID",
                error_message=str(exc),
            )

        if len(raw_table.rows) == 0:
            return self._error_response(
                request=request_obj,
                error_code="EMPTY_RESULT",
                error_message="Census API returned no data rows",
            )

        records = [
            StrictCensusApiRecord(values=dict(zip(raw_table.headers, row)))
            for row in raw_table.rows
        ]

        response = StrictCensusApiResponse(
            success=True,
            request=request_obj,
            headers=raw_table.headers,
            records=records,
            row_count=len(records),
            error=None,
            error_message=None,
        )

        record_event(
            "strict_census_api_call",
            {
                "dataset": request_obj.dataset,
                "year": request_obj.year,
                "variables": request_obj.variables,
                "geo_filters": geo_filters,
                "success": True,
                "row_count": response.row_count,
                "url": result.get("url"),
            },
        )
        logger.info(
            "Strict Census API call succeeded (%s/%s) rows=%s",
            request_obj.dataset,
            request_obj.year,
            response.row_count,
        )

        return response

    async def _arun(
        self,
        tool_input: StrictCensusApiRequest,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> StrictCensusApiResponse:
        # Keep async contract; sync execution is deterministic and already validated.
        return self._run(tool_input)