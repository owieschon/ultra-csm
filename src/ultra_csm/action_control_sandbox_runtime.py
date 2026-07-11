"""Runtime-only database seam for the hosted Action Control sandbox."""

from __future__ import annotations

from collections.abc import Mapping
import os

import psycopg

from ultra_csm.platform.db import assert_rls_safe_role

RUNTIME_DATABASE_URL_ENV = "ULTRA_CSM_DATABASE_URL"


def persistent_database_configured(env: Mapping[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return bool(values.get(RUNTIME_DATABASE_URL_ENV))


def connect_persistent_runtime_database(
    *,
    env: Mapping[str, str] | None = None,
) -> psycopg.Connection:
    values = os.environ if env is None else env
    runtime_url = values.get(RUNTIME_DATABASE_URL_ENV)
    if not runtime_url:
        raise RuntimeError(f"{RUNTIME_DATABASE_URL_ENV} is not set")
    connection = psycopg.connect(runtime_url)
    try:
        assert_rls_safe_role(connection)
    except Exception:
        connection.close()
        raise
    return connection
