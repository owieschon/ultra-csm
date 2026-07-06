"""Postgres boot-tier resolver tests."""

from __future__ import annotations

import os

import pytest

from ultra_csm import platform


def test_resolve_boot_tier_prefers_system(monkeypatch):
    monkeypatch.setattr(platform, "_system_tool", lambda name: f"/system/{name}")

    assert platform.resolve_postgres_boot_tier() == "system"


def test_resolve_boot_tier_requires_system_postgres(monkeypatch):
    monkeypatch.setattr(platform, "_system_tool", lambda name: None)

    with pytest.raises(FileNotFoundError, match="Postgres 16"):
        platform.resolve_postgres_boot_tier()


# --- stale-cluster reaper -----------------------------------------------
#
# The reaper is destructive-operation-adjacent (it can call `pg_ctl stop`
# and `rm -rf` a datadir), so every test here asserts the detection rule
# from both directions: a live postmaster PID must never be touched, and
# only a directory with a genuinely dead/missing postmaster is reaped.


def _write_postmaster_pid(datadir, pid: int) -> None:
    (datadir / "postmaster.pid").write_text(
        f"{pid}\n{datadir}\n1234567890\n5432\n/tmp/fake-sock-dir\n\n\nstopping\n"
    )


def test_reaper_never_touches_a_directory_with_a_live_postmaster_pid(tmp_path, monkeypatch):
    live_dir = tmp_path / "pgdata.livecluster"
    live_dir.mkdir()
    # os.getpid() is this test process itself -- guaranteed alive for the
    # test's duration, the safest possible stand-in for a real live cluster.
    _write_postmaster_pid(live_dir, os.getpid())

    stop_calls = []
    monkeypatch.setattr(
        platform,
        "_resolve_toolchain",
        lambda: platform._Toolchain("system", "/fake/initdb", "/fake/pg_ctl"),
    )
    monkeypatch.setattr(
        platform.subprocess,
        "run",
        lambda *a, **k: stop_calls.append((a, k)),
    )

    reaped = platform.reap_stale_clusters(base=tmp_path)

    assert reaped == []
    assert live_dir.exists(), "a directory with a live postmaster PID must never be removed"
    assert stop_calls == [], "pg_ctl stop must never be invoked against a live cluster"


def test_reaper_reaps_a_directory_with_a_dead_postmaster_pid(tmp_path, monkeypatch):
    orphan_dir = tmp_path / "pgdata.orphaned"
    orphan_dir.mkdir()
    # Fork+immediately-reap a child to get a PID guaranteed dead right now.
    child_pid = os.fork()
    if child_pid == 0:
        os._exit(0)
    os.waitpid(child_pid, 0)
    _write_postmaster_pid(orphan_dir, child_pid)

    stop_calls = []
    monkeypatch.setattr(
        platform,
        "_resolve_toolchain",
        lambda: platform._Toolchain("system", "/fake/initdb", "/fake/pg_ctl"),
    )

    def _fake_run(cmd, **kwargs):
        stop_calls.append(cmd)
        return None

    monkeypatch.setattr(platform.subprocess, "run", _fake_run)

    reaped = platform.reap_stale_clusters(base=tmp_path)

    assert len(reaped) == 1
    assert reaped[0].datadir == str(orphan_dir)
    assert reaped[0].postmaster_pid == child_pid
    assert not orphan_dir.exists(), "a genuinely orphaned datadir should be removed"
    assert len(stop_calls) == 1
    assert stop_calls[0][:2] == ["/fake/pg_ctl", "-D"]
    assert "-m" in stop_calls[0] and "fast" in stop_calls[0]


def test_reaper_removes_directory_with_no_postmaster_pid_without_calling_pg_ctl(tmp_path, monkeypatch):
    # A pgdata.* dir that's already fully stopped (pg_ctl removed its own
    # pidfile on clean shutdown) has nothing live to stop -- just cleanup.
    already_stopped_dir = tmp_path / "pgdata.alreadystopped"
    already_stopped_dir.mkdir()

    stop_calls = []
    monkeypatch.setattr(platform.subprocess, "run", lambda *a, **k: stop_calls.append(a))

    reaped = platform.reap_stale_clusters(base=tmp_path)

    assert len(reaped) == 1
    assert reaped[0].postmaster_pid is None
    assert reaped[0].stop_attempted is False
    assert not already_stopped_dir.exists()
    assert stop_calls == [], "no postmaster.pid means nothing to stop"


def test_reaper_ignores_non_pgdata_directories(tmp_path, monkeypatch):
    other_dir = tmp_path / "lane-f-tick"
    other_dir.mkdir()

    reaped = platform.reap_stale_clusters(base=tmp_path)

    assert reaped == []
    assert other_dir.exists()


def test_reaper_handles_missing_base_directory(tmp_path):
    missing = tmp_path / "does-not-exist"

    assert platform.reap_stale_clusters(base=missing) == []
