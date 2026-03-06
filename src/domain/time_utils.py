"""
Time and date utility functions for the Census app
"""

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def parse_timestamp(timestamp: Any) -> datetime:
    """Parse various timestamp formats into datetime object"""
    try:
        if isinstance(timestamp, str):
            # Handle ISO format with or without timezone
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif isinstance(timestamp, (int, float)):
            # Handle Unix timestamp
            return datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, datetime):
            return timestamp
        else:
            raise ValueError(f"Unsupported timestamp format: {type(timestamp)}")
    except Exception as e:
        logger.warning(f"Error parsing timestamp {timestamp}: {e}")
        raise


def is_older_than(timestamp: Any, retention_days: int) -> bool:
    """Check if timestamp is older than retention_days"""
    try:
        entry_date = parse_timestamp(timestamp)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        return entry_date < cutoff_date
    except Exception:
        return True  # Consider invalid timestamps as old
