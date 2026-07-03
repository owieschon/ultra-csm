"""Postgres boot-tier resolver tests."""

from __future__ import annotations

import pytest

from ultra_csm import platform


def test_resolve_boot_tier_prefers_system(monkeypatch):
    monkeypatch.setattr(platform, "_system_tool", lambda name: f"/system/{name}")

    assert platform.resolve_postgres_boot_tier() == "system"


def test_resolve_boot_tier_requires_system_postgres(monkeypatch):
    monkeypatch.setattr(platform, "_system_tool", lambda name: None)

    with pytest.raises(FileNotFoundError, match="Postgres 16"):
        platform.resolve_postgres_boot_tier()
