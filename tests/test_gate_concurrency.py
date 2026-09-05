"""Real-concurrency regression for the idempotency lease reclaim race.

`ActionGate.acquire_sim_idempotency_attempt` (gate.py) is the compare-and-set
that lets a committer safely retry after a crash: a `failed` or lease-expired
row may be reclaimed, but only one caller may win a given `idem_key`. Every
existing test for this (test_demo_loop.py::test_sim_committers_recover_pending_crash_reservations)
drives it from ONE connection with sequential calls -- it proves the method's
return values are correct in sequence, not that the underlying SQL is safe
when two independently-connected transactions actually race for the same row
at the same time.

This module races two real `app_runtime` connections (two OS threads, two
psycopg connections, two live Postgres backends) against the same reclaimable
lease, synchronized with a `threading.Barrier` so both issue their competing
UPDATE at the same instant. It establishes -- against the unmodified code --
that Postgres's row lock (not application logic) makes the reclaim atomic:
exactly one thread ever receives a token for a given key, never both, never
neither, and no lease disappears.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import psycopg
import pytest

from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.platform.db import session

_ITERATIONS = 20
_TIMEOUT_S = 10


@dataclass
class _RaceResult:
    token: str | None
    error: BaseException | None


def _seed_failed_lease(gate: ActionGate, idem_key: str) -> None:
    """Put one reclaimable row in place: a lease that a crashed attempt left
    in 'failed' state. This part is single-threaded setup, not the race."""
    first_token = gate.acquire_sim_idempotency_attempt(idem_key)
    assert first_token is not None, "setup: initial acquire must succeed"
    gate.mark_idempotency_failed(idem_key, result_ref="seed", attempt_token=first_token)
    assert gate.idempotency_state(idem_key) == "failed"


def _race_once(gate: ActionGate, idem_key: str, barrier) -> _RaceResult:
    try:
        barrier.wait(timeout=_TIMEOUT_S)
        token = gate.acquire_sim_idempotency_attempt(idem_key)
        return _RaceResult(token=token, error=None)
    except BaseException as exc:  # noqa: BLE001 - surfaced to the assertions below
        return _RaceResult(token=None, error=exc)


@pytest.fixture
def race_tenant(cluster):
    """Two independent app_runtime connections + a scratch tenant_id that
    exists only for the idempotency_keys/audit rows this test writes.

    idempotency_keys.tenant_id/actor_id carry no foreign key (verified against
    migrations/0001_schema.sql, 0003_provenance.sql): a fresh random uuid is a
    valid, RLS-satisfying identity without seeding a tenant/principal roster.
    The idempotency_keys rows are deleted from a bootstrap (RLS-bypassing)
    connection at teardown; audit.change_log is append-only by design and its
    rows for this scratch tenant_id are orphaned but inert.
    """
    tenant_id = str(uuid.uuid4())
    actor_id = str(uuid.uuid4())
    conn_a = psycopg.connect(**cluster.dsn(user="app_runtime"))
    conn_b = psycopg.connect(**cluster.dsn(user="app_runtime"))
    try:
        yield tenant_id, actor_id, conn_a, conn_b
    finally:
        conn_a.close()
        conn_b.close()
        admin = psycopg.connect(**cluster.dsn(user=cluster.BOOTSTRAP_USER))
        try:
            with session(admin, tenant_id=tenant_id, actor_id=actor_id) as cur:
                cur.execute("DELETE FROM idempotency_keys WHERE tenant_id = %s", (tenant_id,))
            # audit.change_log is append-only by design (deny_change_log_mutation);
            # its rows for this scratch, never-reused random tenant_id are
            # orphaned but harmless -- nothing else queries change_log unscoped.
        finally:
            admin.close()


def test_concurrent_lease_reclaim_has_exactly_one_winner(race_tenant):
    """Two live transactions race to reclaim the same failed lease. Exactly
    one must win per attempt; the loser must observe None, never a second
    token, and the row must never end up ownerless (state stuck 'pending'
    with no live owner is the duplicate-execution failure mode this guards)."""
    tenant_id, actor_id, conn_a, conn_b = race_tenant
    gate_a = ActionGate(
        conn_a, tenant_id=tenant_id, actor_principal_id=actor_id,
        verdict_source=FixtureVerdictSource(),
    )
    gate_b = ActionGate(
        conn_b, tenant_id=tenant_id, actor_principal_id=actor_id,
        verdict_source=FixtureVerdictSource(),
    )

    for i in range(_ITERATIONS):
        idem_key = f"race-{i}-{uuid.uuid4()}"
        _seed_failed_lease(gate_a, idem_key)

        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(_race_once, gate_a, idem_key, barrier)
            fut_b = pool.submit(_race_once, gate_b, idem_key, barrier)
            result_a = fut_a.result(timeout=_TIMEOUT_S)
            result_b = fut_b.result(timeout=_TIMEOUT_S)

        assert result_a.error is None, f"iteration {i}: thread A raised {result_a.error!r}"
        assert result_b.error is None, f"iteration {i}: thread B raised {result_b.error!r}"

        tokens = [t for t in (result_a.token, result_b.token) if t is not None]
        assert len(tokens) == 1, (
            f"iteration {i}: expected exactly one winner, got "
            f"a={result_a.token!r} b={result_b.token!r}"
        )

        # The row must be pending, owned by exactly the winner's token -- not
        # left ownerless (which would let a THIRD caller also reclaim it) and
        # not silently re-completed by the loser.
        assert gate_a.idempotency_state(idem_key) == "pending"
        with conn_a.transaction(), conn_a.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, true), "
                "set_config('app.actor_id', %s, true)",
                (tenant_id, actor_id),
            )
            cur.execute(
                "SELECT attempt_token FROM idempotency_keys "
                "WHERE tenant_id = %s AND idem_key = %s",
                (tenant_id, idem_key),
            )
            (stored_token,) = cur.fetchone()
        assert stored_token == tokens[0]
