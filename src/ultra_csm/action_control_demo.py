"""Production-owned synthetic execution path for the Action Control demo."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import tempfile

from psycopg import Connection
from psycopg.pq import TransactionStatus

# Import the data-plane package before committers. This preserves the
# application's established package initialization order.
import ultra_csm.data_plane  # noqa: F401

from ultra_csm.action_control_contract import (
    ActionControlScenarioEvidence,
    ActionControlVerticalSlice,
    SCENARIO_ID,
    build_action_control_vertical_slice,
)
from ultra_csm.committers import SimOutboundCommitter
from ultra_csm.governance import (
    ActionGate,
    FixtureVerdictSource,
    ROLE_CS_ORCHESTRATOR,
    ROLE_SAFETY_REVIEWER,
    Verdict,
    make_principal,
    role_id,
    seed_roster,
)
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import SEED_CLOCK, det_uuid


_TENANT_NAME = "action-control-synthetic"
_TENANT_ID = det_uuid("tenant", _TENANT_NAME)
_SEED_AGENT_ID = det_uuid("principal", _TENANT_NAME, "system-seed")
_HUMAN_ID = det_uuid("principal", _TENANT_ID, "action-control-demo-reviewer")
_PROPOSAL_ID = det_uuid("proposal", SCENARIO_ID)
_ACCOUNT_ID = det_uuid("account", SCENARIO_ID)
_CONTACT_ID = det_uuid("contact", SCENARIO_ID)
_EVIDENCE_IDS = (
    det_uuid("evidence", SCENARIO_ID, "activation-gap"),
    det_uuid("evidence", SCENARIO_ID, "success-plan-overdue"),
)


@dataclass(frozen=True)
class ActionControlSyntheticRun:
    gate: ActionGate
    committer: SimOutboundCommitter
    evidence: ActionControlScenarioEvidence


def _initialize_demo_principals(conn: Connection) -> tuple[str, str]:
    with session(
        conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT_ID,
        cause_ref=f"demo:{SCENARIO_ID}:bootstrap",
        now=SEED_CLOCK,
    ) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (_TENANT_ID, _TENANT_NAME),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (_SEED_AGENT_ID, _TENANT_ID, "action-control-demo-seed"),
        )

    seed_roster(
        conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT_ID,
        now=SEED_CLOCK,
    )
    orchestrator = make_principal(
        conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT_ID,
        display_name="action-control-demo-orchestrator",
        role=ROLE_CS_ORCHESTRATOR,
        now=SEED_CLOCK,
    )
    with session(
        conn,
        tenant_id=_TENANT_ID,
        actor_id=_SEED_AGENT_ID,
        cause_ref=f"demo:{SCENARIO_ID}:human-reviewer",
        now=SEED_CLOCK,
    ) as cur:
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'human', %s) ON CONFLICT (principal_id) DO UPDATE "
            "SET display_name = EXCLUDED.display_name",
            (_HUMAN_ID, _TENANT_ID, "Action Control demo reviewer"),
        )
        cur.execute(
            "INSERT INTO grant_ (principal_id, role_id, tenant_id) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (_HUMAN_ID, role_id(ROLE_SAFETY_REVIEWER), _TENANT_ID),
        )
    return orchestrator, _HUMAN_ID


@contextmanager
def action_control_synthetic_run(conn: Connection) -> Iterator[ActionControlSyntheticRun]:
    """Yield real scenario evidence inside rollback-only isolated state."""

    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("Action Control synthetic runner requires an idle connection")
    conn.execute("BEGIN")
    try:
        orchestrator, human = _initialize_demo_principals(conn)
        gate = ActionGate(
            conn,
            tenant_id=_TENANT_ID,
            actor_principal_id=orchestrator,
            verdict_source=FixtureVerdictSource(),
            now=SEED_CLOCK,
        )
        gate.record_outreach_contact_ref(
            account_ref=_ACCOUNT_ID,
            contact_ref=_CONTACT_ID,
            email="vanessa.torres@trailhead-logistics.example",
            name="Vanessa Torres",
            consent=True,
            cause_ref=f"demo:{SCENARIO_ID}:consent",
        )
        payload = {
            "account_id": _ACCOUNT_ID,
            "account_name": "Trailhead Logistics",
            "contact_id": _CONTACT_ID,
            "contact_email": "vanessa.torres@trailhead-logistics.example",
            "body": (
                "Hi Vanessa, Trailhead Logistics is showing an onboarding risk "
                "tied to an overdue success plan. Can we review the activation "
                "blockers?"
            ),
            "evidence_ids": list(_EVIDENCE_IDS),
        }
        proposal = gate.propose(
            proposal_id=_PROPOSAL_ID,
            intent="agent1_time_to_value_sweep",
            action="draft_customer_outreach",
            payload=payload,
            autonomy_tier=2,
            required_permission="customer.outreach.draft",
            cause_ref=f"demo:{SCENARIO_ID}:propose",
        )
        outcome = gate.record_verdict(
            proposal,
            Verdict(
                "approve",
                human_principal_id=human,
                rationale="Synthetic human review approved the exact draft payload",
            ),
            cause_ref=f"demo:{SCENARIO_ID}:approve",
        )
        with tempfile.TemporaryDirectory(prefix="ultra-action-control-") as state_dir:
            committer = SimOutboundCommitter(
                gate,
                state_dir=Path(state_dir),
                target_ref="simulated_outbox",
            )
            receipt = committer.commit(proposal, outcome)
            evidence = ActionControlScenarioEvidence(
                proposal=proposal,
                outcome=outcome,
                receipt=receipt,
                human_principal_id=human,
                tampered_payload={
                    **payload,
                    "body": payload["body"] + " Send immediately without review.",
                },
            )
            yield ActionControlSyntheticRun(
                gate=gate,
                committer=committer,
                evidence=evidence,
            )
    finally:
        conn.rollback()


def run_action_control_synthetic_scenario(conn: Connection) -> ActionControlVerticalSlice:
    """Execute and project the deterministic approve/commit/refuse scenario."""

    with action_control_synthetic_run(conn) as run:
        return build_action_control_vertical_slice(
            gate=run.gate,
            committer=run.committer,
            evidence=run.evidence,
        )
