"""
File I/O utility functions for the Census app
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_json_file(file_path: Path, default_value: Any = None) -> Any:
    """Load JSON file safely with default fallback"""
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading {file_path}: {e}")
    return default_value


def save_json_file(file_path: Path, data: Any) -> bool:
    """Save JSON file safely"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")
        return False
