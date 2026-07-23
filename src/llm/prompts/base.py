"""Shared contracts for versioned LLM prompts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class VersionedPrompt:
    """A prompt whose identity can be recorded in runtime traces."""

    prompt_id: str
    version: str
    role: str
    template: str

    @property
    def trace_metadata(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                "prompt_id": self.prompt_id,
                "prompt_version": self.version,
                "prompt_role": self.role,
            }
        )

    def render(self, **values: str) -> str:
        body = self.template.format(**values)
        return f"[prompt_id={self.prompt_id} prompt_version={self.version} prompt_role={self.role}]\n{body}"


__all__ = ["VersionedPrompt"]
