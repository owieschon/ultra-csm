"""DB-layer proof of cross-tenant containment via FORCE ROW LEVEL SECURITY.

The sweep-level `H_cross_tenant` hard gate (eval/scorecard_csm.py::_assert_cross_tenant,
asserted in tests/test_scorecard_csm.py) proves no leak at the APPLICATION layer: the
sweep's own output never references a decoy tenant's data. It says nothing about
whether the DB's tenant_isolation FORCE RLS policy (migrations/0002_rls.sql) would
itself block a cross-tenant read if the application-level filtering were ever wrong
or bypassed. This file proves the DB layer directly, using the same asymmetry
argument 0002_rls.sql's own comment names: the app_runtime role (NOSUPERUSER
NOBYPASSRLS) is subject to FORCE RLS, while the bootstrap/superuser role bypasses
it -- so the SAME query, unfiltered, returns different results depending on which
role runs it. That asymmetry is the proof the policy (not an accidental
application-level WHERE clause) is what enforces isolation.

Uses the existing, previously-unused `bootstrap_conn`/`T2`/`T2_AGENT` fixtures
(conftest.py / tests/_govhelpers.py) purpose-built for exactly this. Does not
duplicate or modify the existing H_cross_tenant sweep-level test, which stays
valid and unchanged.
"""

from __future__ import annotations

import psycopg
import pytest

from ultra_csm.platform.db import UnsafeDbRole, assert_rls_safe_role, session

from tests._govhelpers import CLOCK, T1, T1_AGENT, T2, T2_AGENT


def test_runtime_role_passes_rls_safety_guard(runtime_conn):
    assert_rls_safe_role(runtime_conn)


def test_superuser_role_fails_rls_safety_guard(bootstrap_conn):
    with pytest.raises(UnsafeDbRole, match="bypasses RLS"):
        assert_rls_safe_role(bootstrap_conn)


def _write_principal_as_t1(runtime_conn: psycopg.Connection) -> str:
    """Write one principal row scoped to tenant T1 via the real app_runtime
    role + session() seam (the same write path production code uses)."""
    display_name = "cross-tenant-rls-probe"
    with session(runtime_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (gen_random_uuid(), %s, 'human', %s) RETURNING principal_id",
            (T1, display_name),
        )
        principal_id = str(cur.fetchone()[0])
    return principal_id


def _count_visible(conn: psycopg.Connection, *, tenant_id: str, actor_id: str,
                    principal_id: str) -> int:
    """How many rows with this principal_id are visible to a session bound to
    *tenant_id* -- no application-level WHERE tenant_id filter here at all;
    visibility is left entirely to whatever RLS policy is (or isn't) active."""
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=CLOCK) as cur:
        cur.execute(
            "SELECT count(*) FROM principal WHERE principal_id = %s", (principal_id,)
        )
        return cur.fetchone()[0]


def test_cross_tenant_rls_blocks_read_across_tenants(runtime_conn):
    """A row written under tenant T1 (via the real app_runtime role) is
    invisible to an app_runtime session bound to tenant T2 -- the FORCE RLS
    policy itself, not application-level filtering, is what hides it."""
    principal_id = _write_principal_as_t1(runtime_conn)

    same_tenant_count = _count_visible(
        runtime_conn, tenant_id=T1, actor_id=T1_AGENT, principal_id=principal_id)
    cross_tenant_count = _count_visible(
        runtime_conn, tenant_id=T2, actor_id=T2_AGENT, principal_id=principal_id)

    assert same_tenant_count == 1
    assert cross_tenant_count == 0


def test_cross_tenant_rls_asymmetry_proves_it_is_rls_not_an_accident(
    runtime_conn, bootstrap_conn
):
    """The asymmetry 0002_rls.sql's own comment names as the proof: the SAME
    unfiltered query, bound to tenant T2, sees nothing over app_runtime (RLS
    enforced) but DOES see the T1 row over the bootstrap/superuser role (RLS
    bypassed by design for that role). If this ever returned 0 for BOTH roles,
    that would mean the row simply isn't there (a fixture bug); seeing it
    only when RLS is bypassed is what proves RLS -- not some other
    accidental filter -- is the enforcement mechanism."""
    principal_id = _write_principal_as_t1(runtime_conn)

    blocked = _count_visible(
        runtime_conn, tenant_id=T2, actor_id=T2_AGENT, principal_id=principal_id)
    bypassed = _count_visible(
        bootstrap_conn, tenant_id=T2, actor_id=T2_AGENT, principal_id=principal_id)

    assert blocked == 0
    assert bypassed == 1


def test_cross_tenant_rls_test_itself_fails_if_the_policy_is_broken(cluster):
    """Proves the test above is not a false negative: with tenant_isolation
    replaced by a too-permissive policy (`USING (true)` -- the realistic
    shape of a real regression: someone edits/rewrites the policy and drops
    the tenant_id predicate, exactly what a future migration author could do
    by accident), the SAME cross-tenant read now leaks -- i.e. this suite's
    cross-tenant assertion WOULD catch that regression.

    DROP POLICY outright was tried first and rejected on two counts (K5:
    same failure twice would mean changing approach, but here two DISTINCT
    problems each independently ruled it out, worth recording both): (1) a
    second connection performing the concurrent read deadlocks against the
    DROP's lock -- observed directly (`PARSE waiting` vs `idle in
    transaction`); (2) even fixed to run on one connection, Postgres's
    documented default-deny behavior for ENABLE ROW LEVEL SECURITY with ZERO
    policies defined is to deny ALL rows to non-owners (fail-closed, not
    fail-open) -- verified empirically: dropping the only policy produced
    `count == 0` for BOTH same-tenant and cross-tenant reads, not a leak.
    Replacing the policy with an unconditionally-true USING clause is the
    only way to simulate an actual leaky-policy regression, and is also the
    realistic failure shape a broken migration would take.

    Everything runs on ONE connection (superuser, so it can rewrite the
    policy and SET ROLE) inside a single transaction that is always rolled
    back -- DDL is transactional in Postgres, so the real policy is restored
    even on failure, and it is never left disabled or replaced outside this
    transaction. SET LOCAL ROLE (not plain SET ROLE) keeps the role switch
    scoped to this transaction, reverting automatically at ROLLBACK."""
    admin = psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER))
    try:
        admin.execute("BEGIN")
        admin.execute("DROP POLICY tenant_isolation ON principal")
        admin.execute(
            "CREATE POLICY tenant_isolation ON principal USING (true) WITH CHECK (true)"
        )

        with session(admin, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
            cur.execute(
                "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
                "VALUES (gen_random_uuid(), %s, 'human', %s) RETURNING principal_id",
                (T1, "policy-broken-probe"),
            )
            principal_id = str(cur.fetchone()[0])

        admin.execute("SET LOCAL ROLE app_runtime")
        leaked_count = _count_visible(
            admin, tenant_id=T2, actor_id=T2_AGENT, principal_id=principal_id)

        assert leaked_count == 1, (
            "policy-broken probe expected a leak (proving the assertion "
            "would catch a real regression); got no leak instead -- the "
            "permissive policy may not have taken effect as expected"
        )
    finally:
        admin.rollback()  # restores the real policy AND the role; never left broken.
        admin.close()
