"""Postgres boot-tier resolver tests."""

from __future__ import annotations

import sys
import types

from ultra_csm import platform


def test_resolve_boot_tier_prefers_system(monkeypatch):
    monkeypatch.setattr(platform, "_system_tool", lambda name: f"/system/{name}")

    assert platform.resolve_postgres_boot_tier() == "system"


def test_resolve_boot_tier_falls_back_to_pgserver(monkeypatch, tmp_path):
    package = tmp_path / "pgserver"
    bindir = package / "bin"
    bindir.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name in ("initdb", "pg_ctl"):
        (bindir / name).write_text("", encoding="utf-8")

    module = types.ModuleType("pgserver")
    module.__file__ = str(package / "__init__.py")
    monkeypatch.setitem(sys.modules, "pgserver", module)
    monkeypatch.setattr(platform, "_system_tool", lambda name: None)

    assert platform.resolve_postgres_boot_tier() == "pgserver"
