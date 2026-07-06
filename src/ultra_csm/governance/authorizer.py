"""The RBAC authorizer: permission lookup over grant_ -> role_permission ->
permission.

`has_permission` is the §7 autonomy gate reduced to a *lookup* (does this
principal hold the permission this action requires?) rather than hard-coded
logic. It runs through `session()` so RLS scopes the query to the acting
tenant; the answer is fail-closed (a principal with no matching grant → False).
"""

from __future__ import annotations

import hashlib
import json

from ultra_csm.platform.db import session
from ultra_csm.platform.seed import det_uuid as _det

ROLE_SAFETY_REVIEWER = "safety_reviewer"
ROLE_CS_ORCHESTRATOR = "cs_orchestrator"

ROLES = (
    ROLE_CS_ORCHESTRATOR,
    ROLE_SAFETY_REVIEWER,
)

ROLE_PERMISSIONS = {
    "governance.review": ROLE_SAFETY_REVIEWER,
    "csm.recommend": ROLE_CS_ORCHESTRATOR,
    "customer.outreach.draft": ROLE_CS_ORCHESTRATOR,
    "crm.activity.write": ROLE_CS_ORCHESTRATOR,
    "cs_platform.record.write": ROLE_CS_ORCHESTRATOR,
    "cs_platform.success_plan.write": ROLE_CS_ORCHESTRATOR,
    "customer.call.initiate": ROLE_CS_ORCHESTRATOR,
}


def canonical_payload_sha256(payload: dict) -> str:
    """The anti-TOCTOU binding hash. Canonical = sorted keys, compact separators,
    so the same logical payload always hashes identically (a proposal's hash at
    emit must equal the committer's recompute)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def role_id(name: str) -> str:
    return _det("role", name)


def permission_id(tenant_id: str, name: str) -> str:
    return _det("permission", tenant_id, name)


def seed_roster(conn, *, tenant_id: str, actor_id: str, now=None) -> None:
    """Seed the minimal CSM agent roles and permissions for one tenant."""

    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        for name in ROLES:
            cur.execute(
                "INSERT INTO role (role_id, name) VALUES (%s, %s) "
                "ON CONFLICT (name) DO NOTHING",
                (role_id(name), name),
            )
        for perm in ROLE_PERMISSIONS:
            cur.execute(
                "INSERT INTO permission (permission_id, tenant_id, name) "
                "VALUES (%s, %s, %s) ON CONFLICT (tenant_id, name) DO NOTHING",
                (permission_id(tenant_id, perm), tenant_id, perm),
            )
        for perm, holder_role in ROLE_PERMISSIONS.items():
            cur.execute(
                "INSERT INTO role_permission (role_id, permission_id, tenant_id) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (role_id(holder_role), permission_id(tenant_id, perm), tenant_id),
            )


def make_principal(
    conn,
    *,
    tenant_id: str,
    actor_id: str,
    display_name: str,
    role: str,
    now=None,
) -> str:
    """Create an agent principal and grant it one seeded CSM role."""

    principal_id = _det("principal", tenant_id, display_name)
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (principal_id, tenant_id, display_name),
        )
        cur.execute(
            "INSERT INTO grant_ (principal_id, role_id, tenant_id) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (principal_id, role_id(role), tenant_id),
        )
    return principal_id


class Authorizer:
    """Wraps the same psycopg connection the DomainService uses; identity is
    supplied per call so RLS binds. Read-only: it never mutates."""

    def __init__(self, conn, *, tenant_id: str, actor_id: str, now=None) -> None:
        self._conn = conn
        self._tenant_id = tenant_id
        self._actor_id = actor_id
        self._now = now

    def has_permission(self, principal_id: str, permission: str) -> bool:
        """True iff `principal_id` holds `permission` via any of its roles. The
        query is RLS-scoped to the acting tenant; a cross-tenant principal_id
        therefore resolves to no grant (fail-closed)."""
        with session(self._conn, tenant_id=self._tenant_id,
                     actor_id=self._actor_id, now=self._now) as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM grant_ g "
                "  JOIN role_permission rp ON rp.role_id = g.role_id "
                "  JOIN permission p ON p.permission_id = rp.permission_id "
                "  WHERE g.principal_id = %s AND p.name = %s)",
                (principal_id, permission),
            )
            return bool(cur.fetchone()[0])
