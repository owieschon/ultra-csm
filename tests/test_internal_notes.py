"""internal_note table: RLS isolation + provenance, same discipline as every
other business table (migrations/0005_internal_notes.sql)."""

from __future__ import annotations

from ultra_csm.platform.db import session

from tests._govhelpers import (  # noqa: F401 - gov_conn is a pytest fixture used by injection
    CLOCK,
    T1,
    T1_AGENT,
    T2,
    T2_AGENT,
    change_log_count,
    gov_conn,
    setup_roster,
)


def _seed_account(conn, *, tenant, actor, account_id, name):
    with session(conn, tenant_id=tenant, actor_id=actor, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO account (account_id, tenant_id, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (account_id) DO NOTHING",
            (account_id, tenant, name),
        )


def test_internal_note_insert_and_provenance(gov_conn):
    setup_roster(gov_conn)
    account_id = "11111111-1111-1111-1111-111111111111"
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_id, name="Meridian Fleet")

    with session(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO internal_note (note_id, tenant_id, account_id, author, content, source) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s) RETURNING note_id",
            (T1, account_id, "Marcus Webb", "champion went quiet for 2 weeks", "csm_note"),
        )
        note_id = cur.fetchone()[0]

    assert change_log_count(gov_conn, "internal_note", "note_id", note_id, tenant=T1) == 1


def test_internal_note_source_check_constraint_rejects_unknown_value(gov_conn):
    setup_roster(gov_conn)
    account_id = "22222222-2222-2222-2222-222222222222"
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_id, name="Pinnacle Supply")

    try:
        with session(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
            cur.execute(
                "INSERT INTO internal_note (note_id, tenant_id, account_id, author, content, source) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)",
                (T1, account_id, "someone", "text", "not_a_real_source"),
            )
        raised = False
    except Exception:
        raised = True
    assert raised, "CHECK (source IN ('csm_note', 'slack')) should reject an unknown value"


def test_internal_note_is_tenant_isolated(gov_conn):
    setup_roster(gov_conn, tenant=T1, seed_actor=T1_AGENT)
    setup_roster(gov_conn, tenant=T2, seed_actor=T2_AGENT)
    account_id = "33333333-3333-3333-3333-333333333333"
    _seed_account(gov_conn, tenant=T1, actor=T1_AGENT, account_id=account_id, name="Crateworks")

    with session(gov_conn, tenant_id=T1, actor_id=T1_AGENT, now=CLOCK) as cur:
        cur.execute(
            "INSERT INTO internal_note (note_id, tenant_id, account_id, author, content, source) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)",
            (T1, account_id, "someone", "T1-only note", "csm_note"),
        )

    with gov_conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (T2,))
        cur.execute("SELECT count(*) FROM internal_note WHERE account_id = %s", (account_id,))
        assert cur.fetchone()[0] == 0, "T2 must not see T1's internal_note row (RLS)"
