"""Deterministic-overlap regression for the idempotency lease reclaim.

Scope: this exercises exactly one primitive --
`ActionGate.acquire_sim_idempotency_attempt` (gate.py) -- the compare-and-set
a committer uses to safely retry after a crash. It does NOT invoke a
committer, does not write an outbox/CRM record, and does not prove anything
about a complete committed action or a prevented duplicate customer send.
Those live in `SimOutboundCommitter`/`SimCrmActivityCommitter` and are out of
scope for this file.

The existing crash-recovery coverage
(test_demo_loop.py::test_sim_committers_recover_pending_crash_reservations)
drives the lease from ONE connection with sequential calls: it proves the
method's return values are correct in sequence, not that the underlying SQL
is safe when two independently-connected transactions actually contend for
the same row at the same time. A `threading.Barrier` released just before two
calls does not, by itself, prove the two DB statements ever overlapped --
removing the SQL guard can still produce two winners on two *sequential*
statements if the timing doesn't line up, which would make that shape of
test pass or fail on luck rather than mechanism.

This test instead forces and *observes* real overlap: connection A opens the
row via the reclaim UPDATE inside an explicit transaction it does not yet
commit, holding a live Postgres row lock. Connection B, on an independent
backend, issues the identical reclaim UPDATE for the same key on its own
thread. Before A is allowed to commit, a third (admin) connection polls
`pg_blocking_pids()` and asserts B's backend PID is observed as blocked on
A's backend PID -- a DB-level fact, not a timing assumption. Only then does A
commit; B's statement then resolves under the post-commit row state and must
lose (0 rows / None), never a second token.

Runs against a dedicated, self-contained ephemeral Postgres cluster (booted
and torn down within this module) rather than the shared session-scoped
`cluster` fixture in conftest.py, so this test can never leave rows behind in
state other tests observe.
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

import psycopg
import pytest

from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.platform import boot_seeded_cluster

_REPO = Path(__file__).resolve().parents[1]
_MIGRATIONS = _REPO / "migrations"
_BLOCK_WAIT_S = 5.0
_STATEMENT_TIMEOUT_MS = 5000


@pytest.fixture(scope="module")
def gate_cluster():
    """A dedicated ephemeral cluster, isolated from every other test file's
    shared session-scoped `cluster` (conftest.py) -- booted and fully torn
    down here, so this module can never contaminate it."""
    with boot_seeded_cluster(_MIGRATIONS) as (cluster, _dsn):
        yield cluster


def _backend_pid(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT pg_backend_pid()").fetchone()[0]


def _wait_until_blocked_on(admin: psycopg.Connection, *, blocked_pid: int,
                            blocker_pid: int, timeout_s: float) -> bool:
    """Poll pg_blocking_pids() -- the DB's own lock-wait graph, not a guess
    from application-side timing -- until `blocked_pid` is reported as
    waiting on `blocker_pid`, or the bound elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        row = admin.execute(
            "SELECT pg_blocking_pids(%s)", (blocked_pid,)
        ).fetchone()
        blockers = row[0] if row else []
        if blocker_pid in blockers:
            return True
        time.sleep(0.02)
    return False


def test_lease_reclaim_serializes_under_db_observed_lock_contention(gate_cluster):
    """Connection B's competing reclaim is proven DB-blocked on connection A
    before A releases; once released, B must lose the reclaim outright."""
    tenant_id = str(uuid.uuid4())
    actor_id = str(uuid.uuid4())
    idem_key = f"lock-proof-{uuid.uuid4()}"

    conn_a = psycopg.connect(**gate_cluster.dsn(user="app_runtime"))
    conn_b = psycopg.connect(**gate_cluster.dsn(user="app_runtime"))
    admin = psycopg.connect(**gate_cluster.dsn(user=gate_cluster.BOOTSTRAP_USER))
    try:
        conn_b.execute(f"SET statement_timeout = {_STATEMENT_TIMEOUT_MS}")

        gate_a = ActionGate(conn_a, tenant_id=tenant_id, actor_principal_id=actor_id,
                            verdict_source=FixtureVerdictSource())
        gate_b = ActionGate(conn_b, tenant_id=tenant_id, actor_principal_id=actor_id,
                            verdict_source=FixtureVerdictSource())

        # Single-connection setup (not the proof): seed a reclaimable lease
        # the way a crashed committer attempt would leave one.
        seed_token = gate_a.acquire_sim_idempotency_attempt(idem_key)
        assert seed_token is not None
        gate_a.mark_idempotency_failed(idem_key, result_ref="seed", attempt_token=seed_token)
        assert gate_a.idempotency_state(idem_key) == "failed"

        pid_a = _backend_pid(conn_a)
        pid_b = _backend_pid(conn_b)

        # A opens the reclaim inside an explicit, not-yet-committed
        # transaction: the row lock it takes is held until conn_a.commit(),
        # regardless of what session()'s internal SAVEPOINT does.
        conn_a.execute("BEGIN")
        token_a = gate_a.acquire_sim_idempotency_attempt(idem_key)
        assert token_a is not None

        outcome: dict[str, object] = {}

        def _contend() -> None:
            try:
                outcome["token"] = gate_b.acquire_sim_idempotency_attempt(idem_key)
            except BaseException as exc:  # noqa: BLE001 - surfaced by the assertions below
                outcome["error"] = exc

        thread_b = threading.Thread(target=_contend, daemon=True)
        thread_b.start()
        try:
            blocked = _wait_until_blocked_on(
                admin, blocked_pid=pid_b, blocker_pid=pid_a, timeout_s=_BLOCK_WAIT_S,
            )
        finally:
            # Release A's lock unconditionally -- if the block was never
            # observed, this still unblocks B's daemon thread so the process
            # cannot hang, and statement_timeout on conn_b is the hard
            # backstop if it somehow does not.
            conn_a.commit()
        thread_b.join(timeout=_BLOCK_WAIT_S)

        assert blocked, (
            "connection B was never DB-observed (pg_blocking_pids) as "
            "blocked on connection A's held row lock -- no genuine overlap "
            "occurred, so this run proves nothing about serialization"
        )
        assert not thread_b.is_alive(), "contending thread did not finish after A released its lock"
        assert "error" not in outcome, f"contending thread raised {outcome.get('error')!r}"
        assert outcome.get("token") is None, (
            "connection B must lose the reclaim once A's committed row is "
            "no longer 'failed' -- a non-None token here is the exact "
            "duplicate-reservation defect this test guards against"
        )

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
        assert stored_token == token_a
    finally:
        conn_a.close()
        conn_b.close()
        admin.close()
