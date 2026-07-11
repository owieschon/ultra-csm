"""Synthetic identities used by the isolated Action Control sandbox only."""

from __future__ import annotations

from psycopg import Connection

from ultra_csm.action_control_contract import SCENARIO_ID
from ultra_csm.governance import (
    ROLE_CS_ORCHESTRATOR,
    ROLE_SAFETY_REVIEWER,
    make_principal,
    role_id,
    seed_roster,
)
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import SEED_CLOCK, det_uuid

TENANT_NAME = "action-control-synthetic"
TENANT_ID = det_uuid("tenant", TENANT_NAME)
SEED_AGENT_ID = det_uuid("principal", TENANT_NAME, "system-seed")
HUMAN_ID = det_uuid("principal", TENANT_ID, "action-control-demo-reviewer")
PROPOSAL_ID = det_uuid("proposal", SCENARIO_ID)
ACCOUNT_ID = det_uuid("account", SCENARIO_ID)
CONTACT_ID = det_uuid("contact", SCENARIO_ID)
EVIDENCE_IDS = (
    det_uuid("evidence", SCENARIO_ID, "activation-gap"),
    det_uuid("evidence", SCENARIO_ID, "success-plan-overdue"),
)


def initialize_sandbox_principals(conn: Connection) -> tuple[str, str]:
    """Create only the deterministic principals needed by the sandbox transaction."""

    with session(
        conn,
        tenant_id=TENANT_ID,
        actor_id=SEED_AGENT_ID,
        cause_ref=f"sandbox:{SCENARIO_ID}:bootstrap",
        now=SEED_CLOCK,
    ) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (TENANT_ID, TENANT_NAME),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (SEED_AGENT_ID, TENANT_ID, "action-control-sandbox-seed"),
        )

    seed_roster(
        conn,
        tenant_id=TENANT_ID,
        actor_id=SEED_AGENT_ID,
        now=SEED_CLOCK,
    )
    orchestrator = make_principal(
        conn,
        tenant_id=TENANT_ID,
        actor_id=SEED_AGENT_ID,
        display_name="action-control-sandbox-orchestrator",
        role=ROLE_CS_ORCHESTRATOR,
        now=SEED_CLOCK,
    )
    with session(
        conn,
        tenant_id=TENANT_ID,
        actor_id=SEED_AGENT_ID,
        cause_ref=f"sandbox:{SCENARIO_ID}:human-reviewer",
        now=SEED_CLOCK,
    ) as cur:
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'human', %s) ON CONFLICT (principal_id) DO UPDATE "
            "SET display_name = EXCLUDED.display_name",
            (HUMAN_ID, TENANT_ID, "Action Control sandbox reviewer"),
        )
        cur.execute(
            "INSERT INTO grant_ (principal_id, role_id, tenant_id) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (HUMAN_ID, role_id(ROLE_SAFETY_REVIEWER), TENANT_ID),
        )
    return orchestrator, HUMAN_ID
