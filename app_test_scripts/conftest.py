"""Pytest defaults for runtime modernization tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _classic_runtime_for_offline_tests(request, monkeypatch: pytest.MonkeyPatch):
    """Keep legacy offline tests on classic unless they opt into modern."""
    if request.node.get_closest_marker("modern_runtime"):
        return
    monkeypatch.setenv("AGENT_RUNTIME", "classic")
