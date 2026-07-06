"""Persistent runtime database wiring.

The ephemeral cluster remains the default for tests and local eval. When
``ULTRA_CSM_DATABASE_URL`` is present, served/runtime paths connect to that DSN
as the guarded app role; ``ULTRA_CSM_DATABASE_ADMIN_URL`` optionally supplies
the migration/seed connection for first boot and idempotent upgrades.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import psycopg

from ultra_csm.platform.db import apply_migrations, assert_rls_safe_role
from ultra_csm.platform.seed import seed

RUNTIME_DATABASE_URL_ENV = "ULTRA_CSM_DATABASE_URL"
ADMIN_DATABASE_URL_ENV = "ULTRA_CSM_DATABASE_ADMIN_URL"


def persistent_database_configured(env: Mapping[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return bool(values.get(RUNTIME_DATABASE_URL_ENV))


def persistent_admin_configured(env: Mapping[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return bool(values.get(ADMIN_DATABASE_URL_ENV))


def bootstrap_persistent_database(
    migrations: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Run migrations and base seed against the persistent admin DSN if set.

    Returns True when an admin DSN was present and used. A runtime-only DSN is
    treated as an already-prepared database; the later app_runtime connection
    and queries will fail clearly if the schema is missing.
    """

    values = os.environ if env is None else env
    admin_url = values.get(ADMIN_DATABASE_URL_ENV)
    if not admin_url:
        return False
    with psycopg.connect(admin_url) as boot:
        apply_migrations(boot, migrations)
        seed(boot)
    return True


def connect_persistent_runtime_database(
    *,
    env: Mapping[str, str] | None = None,
) -> psycopg.Connection:
    values = os.environ if env is None else env
    runtime_url = values.get(RUNTIME_DATABASE_URL_ENV)
    if not runtime_url:
        raise RuntimeError(f"{RUNTIME_DATABASE_URL_ENV} is not set")
    conn = psycopg.connect(runtime_url)
    try:
        assert_rls_safe_role(conn)
    except Exception:
        conn.close()
        raise
    return conn
