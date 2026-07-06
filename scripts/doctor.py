"""Preflight check for a fresh clone: verify the environment before the quickstart.

Each check prints PASS/FAIL with the exact fix. The Postgres check boots a real
throwaway cluster — proving the harness works end to end, not just that binaries
exist. Exit code 0 iff everything passed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 10)


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= MIN_PYTHON
    detail = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    fix = f"install Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ and re-run `make setup`"
    return ok, detail if ok else f"{detail} — {fix}"


def check_venv() -> tuple[bool, str]:
    ok = (REPO / ".venv" / "bin" / "python").exists()
    return ok, ".venv present" if ok else "missing — run `make setup`"


def check_pg_binaries() -> tuple[bool, str]:
    try:
        from ultra_csm.platform import resolve_postgres_boot_tier
    except ImportError as exc:
        return False, f"cannot import platform module: {exc} — run `make setup`"
    try:
        resolve_postgres_boot_tier()
    except Exception as exc:  # noqa: BLE001 - report environment resolver failures
        return False, str(exc)
    homebrew = Path("/opt/homebrew/opt/postgresql@16/bin")
    missing = []
    versions = []
    for name in ("initdb", "pg_ctl"):
        found = shutil.which(name) or (homebrew / name if (homebrew / name).exists() else None)
        if found is None:
            missing.append(name)
            continue
        out = subprocess.run(
            [str(found), "--version"], capture_output=True, text=True, timeout=120
        )
        versions.append(out.stdout.strip() or name)
    if missing:
        return False, (
            f"missing {', '.join(missing)} — macOS: `brew install postgresql@16` then add "
            '"$(brew --prefix postgresql@16)/bin" to PATH; Ubuntu: '
            "`sudo apt-get install -y postgresql-16` then add /usr/lib/postgresql/16/bin to PATH"
        )
    return True, "; ".join(versions)


def check_imports() -> tuple[bool, str]:
    try:
        import psycopg  # noqa: F401
        import ultra_csm  # noqa: F401
    except ImportError as exc:
        return False, f"{exc} — run `make setup`"
    return True, "psycopg + ultra_csm import OK"


def check_ephemeral_cluster() -> tuple[bool, str]:
    try:
        from ultra_csm.platform import EphemeralCluster
    except ImportError as exc:
        return False, f"cannot import platform module: {exc} — run `make setup`"
    try:
        with EphemeralCluster() as cluster:
            import psycopg

            with psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER)) as conn:
                encoding = conn.execute("SHOW server_encoding").fetchone()[0]
            tier = cluster.boot_tier
        if encoding != "UTF8":
            return False, f"cluster boots but encoding is {encoding}, expected UTF8"
        return True, f"throwaway cluster booted via {tier}, UTF8, torn down"
    except Exception as exc:  # noqa: BLE001 - report every boot failure with its cause
        log_hint = "check the server.log path in the error output"
        return False, f"cluster failed to boot: {exc} ({log_hint})"


def check_stale_clusters() -> tuple[bool, str]:
    """Preflight-only: reap orphaned ephemeral-Postgres datadirs and report
    what was found. Never fails the overall doctor run -- an orphan found
    and reaped is a thing fixed, not a problem left unresolved."""
    try:
        from ultra_csm.platform import reap_stale_clusters
    except ImportError as exc:
        return False, f"cannot import platform module: {exc} — run `make setup`"
    reaped = reap_stale_clusters()
    if not reaped:
        return True, "no orphaned ephemeral-Postgres clusters found under build/tmp/"
    names = ", ".join(Path(c.datadir).name for c in reaped)
    return True, f"reaped {len(reaped)} orphaned cluster(s): {names}"


CHECKS = (
    ("python", check_python),
    ("venv", check_venv),
    ("postgres binaries", check_pg_binaries),
    ("package imports", check_imports),
    ("ephemeral cluster", check_ephemeral_cluster),
    ("stale cluster reaper", check_stale_clusters),
)


def main() -> int:
    failed = 0
    for name, check in CHECKS:
        ok, detail = check()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            failed += 1
    if failed:
        print(f"\n{failed} check(s) failed — fix the FAIL lines above, then re-run `make doctor`.")
        return 1
    print("\nAll checks passed. Try: make scorecard-csm && make eval && make demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
