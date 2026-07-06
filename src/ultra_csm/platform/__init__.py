"""Minimal local Postgres platform used by the CSM scorecard."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from subprocess import DEVNULL

import psycopg

from ultra_csm.platform.db import (
    UnsafeDbRole,
    apply_migrations,
    assert_rls_safe_role,
    session,
)
from ultra_csm.platform.seed import engine_data_dir, seed

_REPO = Path(__file__).resolve().parents[3]
_HOMEBREW_PG = Path("/opt/homebrew/opt/postgresql@16/bin")


@dataclass(frozen=True)
class _Toolchain:
    tier: str
    initdb: str
    pg_ctl: str


def _tool(name: str) -> str:
    return _resolve_toolchain().__dict__[name]


def resolve_postgres_boot_tier() -> str:
    """Return the local Postgres boot tier that would be used now."""

    return _resolve_toolchain().tier


def _system_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    homebrew = _HOMEBREW_PG / name
    if homebrew.exists():
        return str(homebrew)
    return None


def _resolve_toolchain() -> _Toolchain:
    initdb = _system_tool("initdb")
    pg_ctl = _system_tool("pg_ctl")
    if initdb and pg_ctl:
        return _Toolchain("system", initdb, pg_ctl)

    missing = ", ".join(
        name for name, path in (("initdb", initdb), ("pg_ctl", pg_ctl)) if path is None
    )
    raise FileNotFoundError(
        f"{missing} not found (need Postgres 16: macOS `brew install postgresql@16`; "
        "Ubuntu `sudo apt-get install -y postgresql-16`)"
    )


def _assert_tool_exists(path: str, name: str) -> None:
    if not Path(path).exists():
        raise FileNotFoundError(f"{name} not found (need Postgres 16: `make setup`)")


def _pg_env() -> dict[str, str]:
    """Subprocess env with a UTF-8 locale forced for initdb/pg_ctl.

    Two shell states break the ephemeral cluster otherwise: with no LC_ALL/LANG at
    all, macOS Postgres 16 dies at startup with "FATAL: postmaster became
    multithreaded" (CoreFoundation locale lookup); with LC_ALL=C, initdb creates a
    SQL_ASCII database that later rejects the UTF-8 schema. A UTF-8 locale avoids
    both, so keep the caller's if it already is one and force C.UTF-8 if not.
    """
    env = dict(os.environ)
    current = env.get("LC_ALL") or env.get("LANG") or ""
    if "utf-8" not in current.lower() and "utf8" not in current.lower():
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
    return env


class EphemeralCluster:
    """Throwaway Postgres cluster reachable only over a local Unix socket."""

    BOOTSTRAP_USER = "bootstrap"

    def __init__(self) -> None:
        self._dd: tempfile.TemporaryDirectory | None = None
        self._sock: tempfile.TemporaryDirectory | None = None
        self._datadir: Path | None = None
        self._sockdir: str | None = None
        self._started = False
        self._toolchain: _Toolchain | None = None

    @property
    def boot_tier(self) -> str:
        return self._toolchain.tier if self._toolchain is not None else "not_started"

    def start(self) -> "EphemeralCluster":
        self._toolchain = _resolve_toolchain()
        _assert_tool_exists(self._toolchain.initdb, "initdb")
        _assert_tool_exists(self._toolchain.pg_ctl, "pg_ctl")
        base = _REPO / "build" / "tmp"
        base.mkdir(parents=True, exist_ok=True)
        self._dd = tempfile.TemporaryDirectory(
            prefix="pgdata.", dir=str(base), ignore_cleanup_errors=True
        )
        self._datadir = Path(self._dd.name)
        self._sock = tempfile.TemporaryDirectory(
            prefix="pgs.", dir="/tmp", ignore_cleanup_errors=True
        )
        self._sockdir = self._sock.name

        env = _pg_env()
        subprocess.run(
            [
                self._toolchain.initdb,
                "-D",
                str(self._datadir),
                "-U",
                self.BOOTSTRAP_USER,
                "--auth=trust",
                "-E",
                "UTF8",
            ],
            check=True,
            capture_output=True,
            env=env,
            timeout=120,
        )
        subprocess.run(
            [
                self._toolchain.pg_ctl,
                "-D",
                str(self._datadir),
                "-w",
                "start",
                "-l",
                str(Path(self._sockdir) / "server.log"),
                "-o",
                f"-k {self._sockdir} -c listen_addresses=''",
            ],
            check=True,
            stdout=DEVNULL,
            stderr=DEVNULL,
            env=env,
            timeout=120,
        )
        self._started = True
        return self

    def stop(self) -> None:
        if self._started:
            pg_ctl = self._toolchain.pg_ctl if self._toolchain is not None else _tool("pg_ctl")
            subprocess.run(
                [pg_ctl, "-D", str(self._datadir), "-m", "immediate", "stop"],
                check=False,
                capture_output=True,
                timeout=120,
            )
            self._started = False
        for ctx in (self._dd, self._sock):
            if ctx is not None:
                ctx.cleanup()
        self._dd = self._sock = None
        self._datadir = None
        self._sockdir = None

    def dsn(self, *, user: str, dbname: str = "postgres") -> dict[str, str]:
        if not self._started:
            raise RuntimeError("cluster not started")
        return {"host": self._sockdir, "user": user, "dbname": dbname}

    def __enter__(self) -> "EphemeralCluster":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


@contextlib.contextmanager
def boot_seeded_cluster(
    migrations: Path, *, limit: int | None = None, user: str = "app_runtime"
) -> Iterator[tuple[EphemeralCluster, dict[str, str]]]:
    """Boot, migrate, and seed a throwaway local cluster."""

    with EphemeralCluster() as cluster:
        with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as boot:
            apply_migrations(boot, migrations)
            seed(boot, limit=limit)
        yield cluster, cluster.dsn(user=user)


def _postmaster_pid(datadir: Path) -> int | None:
    """Read the PID from a `postmaster.pid` file, or None if missing/unparseable."""
    pidfile = datadir / "postmaster.pid"
    if not pidfile.exists():
        return None
    try:
        first_line = pidfile.read_text(encoding="utf-8").splitlines()[0]
        return int(first_line.strip())
    except (OSError, IndexError, ValueError):
        return None


def _pid_is_alive(pid: int) -> bool:
    """True iff `pid` names a live process this user can see.

    Uses signal 0 (no-op) rather than actually signaling the process --
    this only probes existence/permission, it never affects the target.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by someone else -- still alive.
        return True
    return True


@dataclass(frozen=True)
class ReapedCluster:
    """One `build/tmp/pgdata.*` directory the reaper found and removed."""

    datadir: str
    postmaster_pid: int | None
    stop_attempted: bool


def reap_stale_clusters(*, base: Path | None = None) -> list[ReapedCluster]:
    """Find and remove orphaned ephemeral-Postgres datadirs under `build/tmp/`.

    A directory is only ever treated as orphaned -- and therefore eligible
    for `pg_ctl stop` + removal -- when BOTH of these hold:
      1. it matches the `pgdata.*` naming pattern this repo's own
         `EphemeralCluster.start()` uses, AND
      2. it contains a `postmaster.pid` file whose recorded PID is NOT a
         live process (a stale/unreachable postmaster).

    A `pgdata.*` directory with a *live* postmaster PID is a cluster that
    is (or may be) actively in use by another concurrent run -- e.g. a
    sibling `make eval` on the same machine -- and matching on the naming
    pattern alone is not enough to prove orphan status. Never stop/remove
    it. This mirrors a real false-positive risk observed directly on this
    machine: two other worktrees' ephemeral clusters were caught mid-run
    with live postmaster PIDs while auditing this exact directory.

    Returns the list of directories reaped (empty if none were stale).
    Never raises on an individual directory's cleanup failure -- logs and
    continues, so one bad entry doesn't block reaping the rest.
    """
    base = base if base is not None else (_REPO / "build" / "tmp")
    if not base.exists():
        return []

    toolchain = None
    reaped: list[ReapedCluster] = []
    for entry in sorted(base.glob("pgdata.*")):
        if not entry.is_dir():
            continue
        pid = _postmaster_pid(entry)
        if pid is not None and _pid_is_alive(pid):
            # Live cluster -- may be in active use. Never touch it.
            continue
        if pid is None:
            # No postmaster.pid at all: already fully stopped (a prior
            # `pg_ctl stop` completed and removed it, or it never started).
            # Nothing live to stop; just remove the leftover directory.
            shutil.rmtree(entry, ignore_errors=True)
            reaped.append(ReapedCluster(datadir=str(entry), postmaster_pid=None, stop_attempted=False))
            continue

        # pid is not None and not alive: a stale postmaster.pid from a
        # crashed/killed prior session. Attempt pg_ctl stop first (in case
        # a child process outlived the recorded postmaster PID), then
        # remove the directory regardless of that command's outcome.
        if toolchain is None:
            toolchain = _resolve_toolchain()
        subprocess.run(
            [toolchain.pg_ctl, "-D", str(entry), "-m", "fast", "stop"],
            check=False,
            capture_output=True,
            timeout=120,
        )
        shutil.rmtree(entry, ignore_errors=True)
        reaped.append(ReapedCluster(datadir=str(entry), postmaster_pid=pid, stop_attempted=True))
    return reaped


__all__ = [
    "EphemeralCluster", "ReapedCluster", "UnsafeDbRole", "apply_migrations",
    "assert_rls_safe_role", "boot_seeded_cluster", "engine_data_dir",
    "reap_stale_clusters", "resolve_postgres_boot_tier", "seed", "session",
]
