"""One-time database bootstrap for the hosted Action Control sandbox.

Both DSNs are read from process environment only. Their values are never printed
or written. The admin DSN applies migrations and seed data, then the runtime DSN
is verified as the constrained ``app_runtime`` role.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Mapping

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg import sql

from ultra_csm.platform.db import apply_migrations, assert_rls_safe_role
from ultra_csm.platform.seed import seed

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
ADMIN_ENV = "ULTRA_CSM_DATABASE_ADMIN_URL"
RUNTIME_ENV = "ULTRA_CSM_DATABASE_URL"


def validated_dsns(env: Mapping[str, str]) -> tuple[str, str, str]:
    admin_url = env.get(ADMIN_ENV, "")
    runtime_url = env.get(RUNTIME_ENV, "")
    if not admin_url or not runtime_url:
        raise RuntimeError(f"{ADMIN_ENV} and {RUNTIME_ENV} are required")
    if admin_url == runtime_url:
        raise RuntimeError("admin and runtime DSNs must be different")
    try:
        admin = conninfo_to_dict(admin_url)
        runtime = conninfo_to_dict(runtime_url)
    except Exception as exc:
        raise RuntimeError("database DSN parsing failed") from exc
    if runtime.get("user") != "app_runtime":
        raise RuntimeError("runtime DSN must authenticate as app_runtime")
    password = runtime.get("password", "")
    if len(password) < 24:
        raise RuntimeError("app_runtime password must contain at least 24 characters")
    admin_host = admin.get("host", "")
    runtime_host = runtime.get("host", "")
    if admin_host.endswith(".neon.tech"):
        if "-pooler." in admin_host:
            raise RuntimeError("Neon migration DSN must be direct, not pooled")
        if not runtime_host.endswith(".neon.tech") or "-pooler." not in runtime_host:
            raise RuntimeError("Neon runtime DSN must use the pooled endpoint")
    return admin_url, runtime_url, password


def bootstrap(env: Mapping[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    admin_url, runtime_url, runtime_password = validated_dsns(values)
    with psycopg.connect(admin_url) as admin:
        apply_migrations(admin, MIGRATIONS)
        seed(admin)
        admin.execute(
            sql.SQL(
                "ALTER ROLE app_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS "
                "NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 10 PASSWORD {}"
            ).format(sql.Literal(runtime_password))
        )
        admin.commit()
        role = admin.execute(
            "SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, "
            "rolreplication FROM pg_roles WHERE rolname = 'app_runtime'"
        ).fetchone()
        if role != (True, False, False, False, False, False):
            raise RuntimeError("app_runtime role attributes failed closed verification")

    with psycopg.connect(runtime_url) as runtime:
        assert_rls_safe_role(runtime)
        current_user = runtime.execute("SELECT current_user").fetchone()
        if current_user != ("app_runtime",):
            raise RuntimeError("runtime DSN did not authenticate as app_runtime")


def main() -> int:
    try:
        bootstrap()
    except Exception as exc:
        print(
            f"database bootstrap failed safely ({type(exc).__name__}); no DSN was printed",
            file=sys.stderr,
        )
        return 1
    print("database bootstrap verified: migrations current, seed current, app_runtime RLS-safe")
    print("unset ULTRA_CSM_DATABASE_ADMIN_URL before any Vercel environment update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
