"""Versioned JSON shapes for profile/history/cache persistence (Track 2C + 2E)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.strict_json import JsonMap, empty_json_map

CURRENT_USER_MEMORY_SCHEMA_VERSION: Literal[2] = 2
CURRENT_CACHE_INDEX_SCHEMA_VERSION: Literal[2] = 2


class UserMemoryFileV2(BaseModel):
    """
    Canonical on-disk ``user_<id>.json`` envelope.

    Reads: accept legacy unversioned dicts via ``migrate_user_memory_file``.
    Writes: always emit ``schema_version`` 2.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    user_id: str
    default_geo: JsonMap = Field(default_factory=empty_json_map)
    preferred_dataset: str = "acs/acs5"
    default_year_range: list[int] = Field(default_factory=lambda: [2012, 2023])
    preferred_level: str = "place"
    var_aliases: dict[str, str] = Field(default_factory=dict)
    last_geo: str | None = None
    usage_stats: JsonMap | None = None
    history: list[JsonMap] = Field(default_factory=list)
    last_updated: str | None = None


class CacheIndexFileV2(BaseModel):
    """Canonical ``cache_index_<user>.json`` envelope."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    entries: JsonMap = Field(default_factory=empty_json_map)


def migrate_user_memory_file(raw: dict[str, Any], *, fallback_user_id: str) -> UserMemoryFileV2:
    """Read-time migration from unversioned profile JSON to ``UserMemoryFileV2``."""
    if raw.get("schema_version") == CURRENT_USER_MEMORY_SCHEMA_VERSION:
        return UserMemoryFileV2.model_validate(raw)

    hist_raw = list(raw.get("history") or [])
    history_maps: list[JsonMap] = []
    for row in hist_raw:
        if isinstance(row, JsonMap):
            history_maps.append(row)
        elif isinstance(row, dict):
            history_maps.append(JsonMap.model_validate(row))
        else:
            raise TypeError(f"History row must be dict or JsonMap, got {type(row)}")

    usage = raw.get("usage_stats")
    usage_blob: JsonMap | None = None
    if usage is not None and isinstance(usage, dict):
        usage_blob = JsonMap.model_validate(usage)

    return UserMemoryFileV2(
        user_id=str(raw.get("user_id") or fallback_user_id),
        default_geo=JsonMap.model_validate(raw.get("default_geo") or {}),
        preferred_dataset=str(raw.get("preferred_dataset") or "acs/acs5"),
        default_year_range=list(
            raw.get("default_year_range") or [2012, 2023],
        ),
        preferred_level=str(raw.get("preferred_level") or "place"),
        var_aliases=dict(raw.get("var_aliases") or {}),
        last_geo=raw.get("last_geo"),
        usage_stats=usage_blob,
        history=history_maps,
        last_updated=raw.get("last_updated"),
    )


def migrate_cache_index_file(raw: dict[str, Any]) -> CacheIndexFileV2:
    """Read-time migration: flat legacy map signature -> metadata becomes ``entries``."""
    if raw.get("schema_version") == CURRENT_CACHE_INDEX_SCHEMA_VERSION:
        return CacheIndexFileV2.model_validate(raw)
    legacy = dict(raw)
    legacy.pop("schema_version", None)
    legacy.pop("entries", None)
    return CacheIndexFileV2(entries=JsonMap.model_validate(legacy))


def memory_profile_to_state_profile(doc: UserMemoryFileV2) -> JsonMap:
    """Map persisted profile envelope into ``CensusState.profile`` (typed JSON map)."""
    return JsonMap.model_validate(doc.model_dump(mode="python"))


def cache_index_for_state(doc: CacheIndexFileV2) -> JsonMap:
    """Graph ``cache_index`` channel mirrors flat signature -> JsonMap roots."""
    return doc.entries.model_copy()

