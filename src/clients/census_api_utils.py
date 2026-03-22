"""Census API utilities with typed request/response boundaries."""

import logging
import os
import time
from typing import Any, Iterable
from urllib.parse import quote, urlencode

import requests
from dotenv import load_dotenv

from config import CENSUS_API_BACKOFF_FACTOR, CENSUS_API_MAX_RETRIES, CENSUS_API_TIMEOUT
from src.clients.chroma_utils import validate_and_fix_geo_params
from src.domain.census_client_contract import (
    CensusApiCallFailure,
    CensusApiCallResult,
    CensusApiCallSuccess,
    CensusApiFailureCode,
    CensusApiQueryParams,
    CensusApiRawTable,
    CensusDatasetUrl,
)

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.census.gov/data"
_GEO_SAFE_CHARS = ":/()*"
_CATEGORY_TO_DATASET_PATH = {
    "detail": "acs/acs5",
    "profile": "acs/acs1/profile",
    "subject": "acs/acs5/subject",
    "cprofile": "acs/acs5/cprofile",
    "spp": "acs/acs1/spp",
}


def _combine_geo_in(
    geo_in: dict[str, str] | None,
    chained_in: Iterable[dict[str, str]] | None,
) -> dict[str, str]:
    combined: dict[str, str] = {} if geo_in is None else dict(geo_in)
    if chained_in:
        for in_dict in chained_in:
            if isinstance(in_dict, dict):
                combined.update(in_dict)
    return combined


def _build_query_params(variables: list[str], geo: dict[str, Any]) -> CensusApiQueryParams:
    filters = geo.get("filters", {})
    return CensusApiQueryParams.model_validate(
        {
            "get": variables,
            "for": filters.get("for"),
            "in": filters.get("in"),
            "key": os.getenv("CENSUS_API_KEY"),
        }
    )


def _validated_request_parts(
    dataset: str,
    year: int,
    variables: list[str],
    geo: dict[str, Any],
) -> tuple[CensusDatasetUrl, CensusApiQueryParams]:
    query = _build_query_params(variables=variables, geo=geo)
    root_url = f"{_BASE_URL}/{year}/{dataset}"
    url_model = CensusDatasetUrl.model_validate(
        {
            "dataset": dataset,
            "year": year,
            "root_url": root_url,
        }
    )
    return url_model, query


def _query_params_payload(query: CensusApiQueryParams) -> dict[str, str]:
    # Keep aliased payload contract while ensuring Census expects a single CSV `get` value.
    payload = query.model_dump(by_alias=True, exclude_none=True)
    payload["get"] = ",".join(query.get_vars)
    return payload


def _build_failure(
    url: str,
    attempt: int,
    error_code: CensusApiFailureCode,
    error_message: str,
) -> CensusApiCallResult:
    return CensusApiCallResult(
        failure=CensusApiCallFailure(
            url=url,
            attempt=attempt,
            error_code=error_code,
            error_message=error_message,
        )
    )


def build_geo_filters(
    dataset: str,
    year: int,
    geo_for: dict[str, str],
    geo_in: dict[str, str] | None = None,
    geo_in_chained: Iterable[dict[str, str]] | None = None,
) -> dict[str, str]:
    """Produce encoded `for` / `in` parameters using hierarchy ordering."""
    combined_in = _combine_geo_in(geo_in, geo_in_chained)
    for_token, for_value, ordered_in = validate_and_fix_geo_params(
        dataset=dataset,
        year=year,
        geo_for=geo_for,
        geo_in=combined_in,
    )

    for_clause = f"{for_token}:{for_value}"
    encoded_for = quote(for_clause, safe=_GEO_SAFE_CHARS)

    encoded_in: str | None = None
    if ordered_in:
        in_clause = " ".join(f"{token}:{value}" for token, value in ordered_in)
        encoded_in = quote(in_clause, safe=_GEO_SAFE_CHARS)

    filters: dict[str, str] = {"for": encoded_for}
    if encoded_in:
        filters["in"] = encoded_in
    return filters


def build_census_url(
    dataset: str,
    year: int,
    variables: list[str],
    geo: dict[str, Any],
) -> str:
    """Build a full Census URL string from validated request pieces."""
    url_model, query = _validated_request_parts(
        dataset=dataset,
        year=year,
        variables=variables,
        geo=geo,
    )
    encoded = urlencode(_query_params_payload(query), doseq=False)
    return f"{str(url_model.root_url)}?{encoded}"


def fetch_census_data_typed(
    dataset: str,
    year: int,
    variables: list[str],
    geo: dict[str, Any],
) -> CensusApiCallResult:
    """Fetch Census data with strict typed request/response validation."""
    try:
        url_model, query = _validated_request_parts(
            dataset=dataset,
            year=year,
            variables=variables,
            geo=geo,
        )
        request_url = str(url_model.root_url)
        params = _query_params_payload(query)
    except Exception as exc:
        return _build_failure(
            url=f"{_BASE_URL}/{year}/{dataset}",
            attempt=0,
            error_code="INVALID_REQUEST",
            error_message=str(exc),
        )

    for attempt in range(CENSUS_API_MAX_RETRIES):
        attempt_number = attempt + 1
        try:
            response = requests.get(
                request_url,
                params=params,
                timeout=CENSUS_API_TIMEOUT,
            )
            response_url = str(response.url)

            if response.status_code == 200:
                try:
                    raw_payload = response.json()
                except ValueError as exc:
                    return _build_failure(
                        url=response_url,
                        attempt=attempt_number,
                        error_code="API_PAYLOAD_JSON_INVALID",
                        error_message=str(exc),
                    )
                try:
                    table = CensusApiRawTable.from_api_payload(raw_payload)
                except Exception as exc:
                    return _build_failure(
                        url=response_url,
                        attempt=attempt_number,
                        error_code="API_PAYLOAD_SHAPE_INVALID",
                        error_message=str(exc),
                    )
                return CensusApiCallResult(
                    success=CensusApiCallSuccess(
                        url=response_url,
                        attempt=attempt_number,
                        table=table,
                    )
                )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = (
                    int(retry_after)
                    if retry_after and retry_after.isdigit()
                    else CENSUS_API_BACKOFF_FACTOR * (2**attempt)
                )
                logger.info(
                    "Census API rate limit hit on attempt %s; waiting %ss",
                    attempt_number,
                    wait_time,
                )
                time.sleep(wait_time)
                continue

            if 500 <= response.status_code < 600:
                wait_time = CENSUS_API_BACKOFF_FACTOR * (2**attempt)
                logger.warning(
                    "Census API server error %s on attempt %s; waiting %ss",
                    response.status_code,
                    attempt_number,
                    wait_time,
                )
                time.sleep(wait_time)
                continue

            return _build_failure(
                url=response_url,
                attempt=attempt_number,
                error_code="HTTP_ERROR",
                error_message=response.text,
            )

        except requests.exceptions.RequestException as exc:
            logger.error("Census API request exception on attempt %s: %s", attempt_number, exc)
            if attempt == CENSUS_API_MAX_RETRIES - 1:
                return _build_failure(
                    url=request_url,
                    attempt=attempt_number,
                    error_code="REQUEST_EXCEPTION",
                    error_message=str(exc),
                )
            wait_time = CENSUS_API_BACKOFF_FACTOR * (2**attempt)
            time.sleep(wait_time)

    return _build_failure(
        url=request_url,
        attempt=CENSUS_API_MAX_RETRIES,
        error_code="MAX_RETRIES_EXCEEDED",
        error_message="Max retries exceeded",
    )


def fetch_census_data(
    dataset: str,
    year: int,
    variables: list[str],
    geo: dict[str, Any],
) -> dict[str, Any]:
    """
    Backward-compatible wrapper around the typed client result.
    Keep until all legacy callers are migrated.
    """
    typed_result = fetch_census_data_typed(
        dataset=dataset,
        year=year,
        variables=variables,
        geo=geo,
    )
    if typed_result.success is not None:
        return {
            "success": True,
            "data": [typed_result.success.table.headers, *typed_result.success.table.rows],
            "url": typed_result.success.url,
            "attempt": typed_result.success.attempt,
        }
    failure = typed_result.failure
    if failure is None:
        return {
            "success": False,
            "error": "INVALID_RESULT: missing success/failure payload",
            "url": "",
            "attempt": 0,
        }
    return {
        "success": False,
        "error": f"{failure.error_code}: {failure.error_message}",
        "url": failure.url,
        "attempt": failure.attempt,
    }


def build_census_url_from_metadata(
    table_metadata: dict[str, Any],
    year: int,
    geo: dict[str, Any],
    variables: list[str] | None = None,
) -> str:
    """Build Census API URL from table metadata."""
    table_code = str(table_metadata["table_code"])
    uses_groups = bool(table_metadata["uses_groups"])
    dataset_path = table_metadata.get("dataset")
    if not dataset_path:
        category = str(table_metadata.get("category", "")).strip().lower()
        dataset_path = _CATEGORY_TO_DATASET_PATH.get(category)
        if dataset_path is None:
            raise ValueError(f"Unsupported table category: {category}")

    get_vars = [f"group({table_code})"] if uses_groups else (variables or [])
    if not get_vars:
        raise ValueError("variables required when uses_groups=False")

    return build_census_url(
        dataset=str(dataset_path),
        year=year,
        variables=get_vars,
        geo=geo,
    )
