"""
Lightweight telemetry helper for recording structured events to logs/telemetry.log.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

TELEMETRY_LOG_DIR = Path("logs")
TELEMETRY_LOG_PATH = TELEMETRY_LOG_DIR / "telemetry.log"

_logger = logging.getLogger("telemetry")
if not _logger.handlers:
    TELEMETRY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(TELEMETRY_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def record_event(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Write a telemetry event as JSON line.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }
    try:
        _logger.info(json.dumps(event))
    except Exception:
        # We intentionally swallow telemetry errors to avoid breaking primary logic.
        pass


__all__ = ["record_event"]

