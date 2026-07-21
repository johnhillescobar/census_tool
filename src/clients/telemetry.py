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

TELEMETRY_LOG_DIR = Path("logs")
TELEMETRY_LOG_PATH = TELEMETRY_LOG_DIR / "telemetry.log"

_logger = logging.getLogger("telemetry")
if not _logger.handlers:
    TELEMETRY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(TELEMETRY_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def record_event(event_type: str, payload: dict[str, Any]) -> None:
    """
    Write a telemetry event as JSON line.
    """
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        **payload,
    }
    try:
        _logger.info(json.dumps(event))
    except Exception as exc:
        print(f"telemetry_write_failed event_type={event_type} error={exc}", file=sys.stderr)
        if os.getenv("CENSUS_TELEMETRY_STRICT", "").strip().lower() in {"1", "true", "yes"}:
            raise


__all__ = ["record_event"]
