"""Migrations + the single identity seam.

`session()` is the one place identity reaches the database: it opens a
transaction and stamps the app.* GUCs (via SET LOCAL, so they are txn-scoped and
pooler-safe) that BOTH row-level security and the provenance trigger read. It
fails closed — no tenant_id/actor_id, no session.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql

# The app.* GUCs the platform recognizes, in the order session() sets them.
# Only tenant_id + actor_id are mandatory; the rest are optional lineage.
_REQUIRED = ("tenant_id", "actor_id", "actor_kind")
_OPTIONAL = ("cause_ref", "request_id", "turn_id", "model_id", "prompt_version", "now")


def apply_migrations(conn: psycopg.Connection, dir: str | Path) -> None:
    """Apply ordered NNNN_*.sql files as the (superuser) bootstrap connection."""
    with conn.cursor() as cur:
        for path in sorted(Path(dir).glob("[0-9]*_*.sql")):
            cur.execute(path.read_text())
    conn.commit()


class UnsafeDbRole(RuntimeError):
    """A runtime connection is bound to a role that can bypass RLS.

    Raised fail-closed by `assert_rls_safe_role` when a runtime DSN points at a
    SUPERUSER or BYPASSRLS role: such a role silently disables FORCE-RLS, so
    tenant isolation and the provenance trigger would be unenforced. The fix is a
    NOSUPERUSER NOBYPASSRLS DSN (the `app_runtime` role), never a code change.
    """


def assert_rls_safe_role(conn: psycopg.Connection) -> None:
    """Fail closed unless `current_user` can be constrained by FORCE-RLS.

    Runtime paths call this once on connect: a DSN accidentally pointed at a
    superuser/BYPASSRLS role would make every tenant policy a silent no-op, so we
    read the role's attributes straight from the catalog and raise `UnsafeDbRole`
    if either is set. The bootstrap connection used for migrations and seed is
    intentionally not guarded.
    """
    # Wrap in conn.transaction() (the session() idiom) so the read commits and the
    # connection returns to IDLE — a persistent runtime connection is reused by
    # session(), which needs the next transaction to be the outermost, not nested.
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        row = cur.fetchone()
    rolsuper, rolbypassrls = row or (False, False)
    if rolsuper or rolbypassrls:
        raise UnsafeDbRole(
            "runtime DB connection is a role that bypasses RLS "
            f"(rolsuper={bool(rolsuper)}, rolbypassrls={bool(rolbypassrls)}); "
            "FORCE-RLS would be silently disabled. Use the NOSUPERUSER "
            "NOBYPASSRLS app_runtime role for runtime connections."
        )


@contextmanager
def session(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    actor_kind: str = "agent",
    cause_ref: str | None = None,
    request_id: str | None = None,
    turn_id: str | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
    now: datetime | str | None = None,
):
    """Transaction-scoped session carrying identity into RLS + provenance.

    Commits on clean exit, rolls back on exception. SET LOCAL keeps every GUC
    bound to this transaction only.
    """
    if not tenant_id or not actor_id:
        raise ValueError("session requires tenant_id and actor_id (fail-closed)")

    values = {
        "tenant_id": tenant_id, "actor_id": actor_id, "actor_kind": actor_kind,
        "cause_ref": cause_ref, "request_id": request_id, "turn_id": turn_id,
        "model_id": model_id, "prompt_version": prompt_version,
        "now": now.isoformat() if isinstance(now, datetime) else now,
    }
    with conn.transaction(), conn.cursor() as cur:
        for key in (*_REQUIRED, *_OPTIONAL):
            val = values[key]
            if val is not None:
                # SET LOCAL won't take a placeholder for the value; use set_config.
                cur.execute(
                    "SELECT set_config(%s, %s, true)", (f"app.{key}", str(val))
                )
        yield cur
