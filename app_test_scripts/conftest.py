"""Pytest defaults for runtime modernization tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _modern_runtime_for_offline_tests(monkeypatch: pytest.MonkeyPatch):
    """Offline tests run against the modern create_agent runtime."""
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)
