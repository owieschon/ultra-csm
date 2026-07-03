"""Minimal local Postgres platform used by the CSM scorecard."""

from __future__ import annotations

import contextlib
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


def _tool(name: str) -> str:
    found = shutil.which(name) or (_HOMEBREW_PG / name)
    if not Path(found).exists():
        raise FileNotFoundError(f"{name} not found (need Postgres 16: `make setup`)")
    return str(found)


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

    def start(self) -> "EphemeralCluster":
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
                _tool("initdb"),
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
        )
        subprocess.run(
            [
                _tool("pg_ctl"),
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
        )
        self._started = True
        return self

    def stop(self) -> None:
        if self._started:
            subprocess.run(
                [_tool("pg_ctl"), "-D", str(self._datadir), "-m", "immediate", "stop"],
                check=False,
                capture_output=True,
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


__all__ = [
    "EphemeralCluster", "UnsafeDbRole", "apply_migrations", "assert_rls_safe_role",
    "boot_seeded_cluster", "engine_data_dir", "seed", "session",
]
