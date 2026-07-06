#!/usr/bin/env python3
"""Provision a local persistent Postgres runtime for the daily operating job."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

import psycopg

from ultra_csm.platform.db import apply_migrations
from ultra_csm.platform.seed import seed

DEFAULT_ROOT = Path.home() / "ultra-csm-persistent-postgres"
DEFAULT_SOCKET_DIR = Path("/tmp/ultracsm-pg")
DEFAULT_ENV_FILE = Path.home() / "ultra-csm-operating.env"


def _tool(name: str) -> str:
    found = shutil.which(name) or f"/opt/homebrew/opt/postgresql@16/bin/{name}"
    if not Path(found).exists():
        raise FileNotFoundError(f"{name} not found")
    return found


def _pg_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("LC_ALL", "en_US.UTF-8")
    env.setdefault("LANG", "en_US.UTF-8")
    return env


def _running(datadir: Path) -> bool:
    result = subprocess.run(
        [_tool("pg_ctl"), "-D", str(datadir), "status"],
        text=True,
        capture_output=True,
        env=_pg_env(),
        check=False,
    )
    return result.returncode == 0


def ensure_cluster(*, root: Path, socket_dir: Path) -> Path:
    datadir = root / "pgdata"
    root.mkdir(parents=True, exist_ok=True)
    socket_dir.mkdir(parents=True, exist_ok=True)
    if not datadir.exists():
        subprocess.run(
            [
                _tool("initdb"),
                "-D",
                str(datadir),
                "-U",
                "bootstrap",
                "--auth=trust",
                "-E",
                "UTF8",
            ],
            check=True,
            capture_output=True,
            env=_pg_env(),
        )
    if not _running(datadir):
        subprocess.run(
            [
                _tool("pg_ctl"),
                "-D",
                str(datadir),
                "-w",
                "start",
                "-l",
                str(root / "server.log"),
                "-o",
                f"-k {socket_dir} -c listen_addresses=''",
            ],
            check=True,
            env=_pg_env(),
        )
    return datadir


def conninfo(*, socket_dir: Path, user: str) -> str:
    return f"host={socket_dir} user={user} dbname=postgres"


def write_env_file(*, env_file: Path, socket_dir: Path) -> None:
    env_file.write_text(
        "\n".join(
            (
                "# Ultra CSM local persistent operating DB. Values are local socket paths only.",
                f"export ULTRA_CSM_DATABASE_ADMIN_URL='{conninfo(socket_dir=socket_dir, user='bootstrap')}'",
                f"export ULTRA_CSM_DATABASE_URL='{conninfo(socket_dir=socket_dir, user='app_runtime')}'",
                "export ULTRA_CSM_DATA_PLANE_MODE='fixture'",
                "",
            )
        ),
        encoding="utf-8",
    )
    env_file.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--socket-dir", type=Path, default=DEFAULT_SOCKET_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)

    ensure_cluster(root=args.root, socket_dir=args.socket_dir)
    migrations = args.repo_root / "migrations"
    with psycopg.connect(conninfo(socket_dir=args.socket_dir, user="bootstrap")) as boot:
        apply_migrations(boot, migrations)
        seed(boot)
    write_env_file(env_file=args.env_file, socket_dir=args.socket_dir)
    print(args.env_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
