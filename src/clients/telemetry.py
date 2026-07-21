"""
Lightweight telemetry helper for recording structured events to logs/telemetry.log.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

TELEMETRY_LOG_DIR = Path("logs")
TELEMETRY_LOG_PATH = TELEMETRY_LOG_DIR / "telemetry.log"
_RESERVED_FIELDS = frozenset({"timestamp", "event_type"})
_CHROMA_COLLECTIONS = frozenset({"census_tables", "census_dataset_geographies", "census_geography_areas"})


class TelemetryEvent(BaseModel):
    """Stable envelope for flattened JSON-line telemetry payloads."""

    model_config = ConfigDict(extra="allow")

    timestamp: datetime
    event_type: str = Field(min_length=1)


_logger = logging.getLogger("telemetry")
if not _logger.handlers:
    TELEMETRY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(TELEMETRY_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def build_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the telemetry envelope and protect its reserved fields."""
    reserved = _RESERVED_FIELDS.intersection(payload)
    if reserved:
        raise ValueError(f"Telemetry payload cannot override reserved fields: {sorted(reserved)}")
    event = TelemetryEvent(
        timestamp=datetime.now(UTC),
        event_type=event_type,
        **payload,
    )
    return event.model_dump(mode="json")


def record_event(event_type: str, payload: dict[str, Any]) -> None:
    """
    Write a telemetry event as JSON line.
    """
    try:
        event = build_event(event_type, payload)
        _logger.info(json.dumps(event))
    except Exception as exc:
        print(f"telemetry_write_failed event_type={event_type} error={exc}", file=sys.stderr)
        if os.getenv("CENSUS_TELEMETRY_STRICT", "").strip().lower() in {"1", "true", "yes"}:
            raise


def release_metrics(events: list[dict[str, Any]], row_results: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Count fail-closed release signals from telemetry and golden-run rows."""
    rows = row_results or []
    return {
        "table_search_events": sum(
            event.get("event_type") == "grounded_retrieval" and event.get("stage") == "table_retrieval" for event in events
        ),
        "geography_blocked": sum(row.get("failure_class") == "geography_blocked" for row in rows),
        "invented_ids": sum(
            event.get("reason_code") == "UNKNOWN_CANDIDATE_ID"
            or bool(set(event.get("selected_ids") or []) - set(event.get("candidate_ids") or []))
            for event in events
        ),
        "implicit_us": sum(
            event.get("geo_for") == {"us": "1"} and not event.get("explicit_geography", False) for event in events
        ),
        "silent_chroma_miss": sum(
            event.get("event_type") == "grounded_retrieval"
            and event.get("collection") in _CHROMA_COLLECTIONS
            and event.get("status") in {"empty", "unavailable", "stale", "schema_mismatch", "error"}
            and not event.get("clarification_required", False)
            for event in events
        ),
    }


__all__ = ["TelemetryEvent", "build_event", "record_event", "release_metrics"]
