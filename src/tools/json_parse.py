"""
Parse the first JSON value from a string. Used by tools when the LLM/framework
may pass concatenated content (e.g. previous observation + next action input),
which would cause json.loads to raise "Extra data".
"""

import json
from typing import Any


def parse_first_json(text: str) -> Any:
    """
    Parse the first complete JSON value from the start of text.
    Trailing content after the first value is ignored.
    Raises json.JSONDecodeError if no valid JSON is found.
    """
    text = text.strip()
    if not text:
        raise json.JSONDecodeError("Empty input", text, 0)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text)
    return obj
