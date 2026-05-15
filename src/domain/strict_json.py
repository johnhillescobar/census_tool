"""Recursive JSON-ish trees for typed state channels (Track 2E).

Nested objects are expressed as plain ``dict[str, JsonNest]`` and lists as
``list[JsonNest]`` — no ambiguous ``typing.Any`` blobs at the CensusState layer.
"""

from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, RootModel, model_validator

JsonScalar: TypeAlias = str | int | float | bool | None

type JsonNest = JsonScalar | list["JsonNest"] | dict[str, "JsonNest"]


def _normalize_nest(obj: object) -> JsonNest:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_normalize_nest(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _normalize_nest(v) for k, v in obj.items()}
    raise TypeError(f"Not JSON-normalizable: {type(obj).__name__}")


class JsonMap(RootModel[dict[str, JsonNest]]):
    """Finite associative JSON subtree (keys are strings)."""

    root: dict[str, JsonNest]

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: object) -> object:
        if isinstance(data, JsonMap):
            return data.root
        if data is None:
            return {}
        if isinstance(data, dict):
            return {str(k): _normalize_nest(v) for k, v in data.items()}
        raise TypeError(f"JsonMap expected dict or JsonMap, got {type(data).__name__}")


def empty_json_map() -> JsonMap:
    return JsonMap(root={})


def _coerce_json_map(value: JsonMap | dict[str, JsonNest] | None) -> JsonMap:
    """Normalize reducer/checkpoint payloads that may arrive as bare dicts."""
    if value is None:
        return JsonMap(root={})
    if isinstance(value, JsonMap):
        return value
    if isinstance(value, dict):
        return JsonMap.model_validate(value)
    raise TypeError(
        "JsonMap coercible value must be JsonMap, dict, or None, "
        f"got {type(value).__name__}"
    )


def as_json_map(value: JsonMap | dict[str, JsonNest] | None) -> JsonMap:
    """Public coercion for checkpoints / LangGraph slices (``None`` → empty map)."""
    return _coerce_json_map(value)


def as_json_map_optional(
    value: JsonMap | dict[str, JsonNest] | None,
) -> JsonMap | None:
    """Like ``as_json_map`` but preserves ``None`` (use for optional intent)."""
    if value is None:
        return None
    return _coerce_json_map(value)


def merge_json_maps(
    existing: JsonMap | dict[str, JsonNest] | None,
    new: JsonMap | dict[str, JsonNest] | None,
) -> JsonMap:
    """Merge roots; tolerant of dict-shaped values from LangGraph checkpoints."""
    e = dict(_coerce_json_map(existing).root)
    n = dict(_coerce_json_map(new).root)
    merged = {**e, **n}
    return JsonMap(root=merged)


class ConversationMessage(BaseModel):
    """Minimal LangChain-compatible chat turn."""

    model_config = ConfigDict(extra="forbid")

    role: str = "user"
    content: str = ""

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_message(cls, data: object) -> object:
        if isinstance(data, ConversationMessage):
            return data
        if isinstance(data, dict):
            role = data.get("role") or data.get("type") or "user"
            raw = data.get("content")
            if raw is None:
                content = ""
            elif isinstance(raw, str):
                content = raw
            else:
                content = str(raw)
            return {"role": str(role), "content": content}
        raise TypeError(
            "ConversationMessage expected dict-shaped LC message or model, "
            f"got {type(data).__name__}"
        )


DEFAULT_AGENT_INTENT = JsonMap(root={"is_census": True, "topic": "general"})

__all__ = [
    "JsonScalar",
    "JsonNest",
    "JsonMap",
    "as_json_map",
    "as_json_map_optional",
    "empty_json_map",
    "merge_json_maps",
    "ConversationMessage",
    "DEFAULT_AGENT_INTENT",
]
