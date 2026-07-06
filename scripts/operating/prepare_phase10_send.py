#!/usr/bin/env python3
"""Prepare the Phase 10 burner send and stop before human approval.

This script is deliberately pre-approval only. It may create one pending
burner-scoped ``draft_customer_outreach`` proposal through ActionGate, then it
builds a sanitized manifest proving the proposal is the only Phase 10
allowlisted pending candidate and that the Gmail committer dry-run path would
not send before the owner records a verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from dotenv import dotenv_values

from ultra_csm.data_plane import DEFAULT_TENANT
from ultra_csm.data_plane.live_facade import build_served_data_plane
from ultra_csm.data_plane.gmail_writeback import (
    RECIPIENT_ALLOWLIST,
    LiveGmailOutboundCommitter,
    ledger_send_count,
)
from ultra_csm.governance import (
    ActionGate,
    ActionProposal,
    FixtureVerdictSource,
    GateOutcome,
    ROLE_CS_ORCHESTRATOR,
    make_principal,
    seed_roster,
)
from ultra_csm.governance.authorizer import canonical_payload_sha256
from ultra_csm.platform.db import session
from ultra_csm.platform.runtime import (
    connect_persistent_runtime_database,
    persistent_database_configured,
)
from ultra_csm.platform.seed import SEED_CLOCK, det_uuid

TENANT_NAME = "acme-csm"
TENANT_ID = det_uuid("tenant", TENANT_NAME)
SEED_AGENT = det_uuid("principal", TENANT_NAME, "system-seed")
PHASE10_MARKER = "phase10_burner_send"
DEFAULT_RUNS_ROOT = Path.home() / "ultra-csm-operating-runs"
DEFAULT_OPERATING_ENV = Path.home() / "ultra-csm-operating.env"
DEFAULT_CREDS_ENV = Path.home() / "ultra-csm-live-creds.env"
REQUIRED_GMAIL_ENV = (
    "ULTRA_CSM_GMAIL_OAUTH_CLIENT_ID",
    "ULTRA_CSM_GMAIL_OAUTH_CLIENT_SECRET",
    "ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN",
    "ULTRA_CSM_GMAIL_SENDER",
)


class Phase10PrepError(RuntimeError):
    """The pre-send manifest could not be prepared safely."""


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _load_env_file(args.operating_env)
    live_env = _merged_env(args.creds_env)

    if not persistent_database_configured():
        raise Phase10PrepError(
            "persistent DB env is not configured; load ULTRA_CSM_DATABASE_URL"
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir = Path(args.ledger_dir or out_dir)
    output_path = Path(args.output or out_dir / "phase10_send_manifest.json")

    with connect_persistent_runtime_database() as conn:
        seed_actor = _ensure_phase10_actor(conn)
        assembly = build_served_data_plane(
            conn=conn,
            comms_tenant_id=TENANT_ID,
            tenant_id=DEFAULT_TENANT,
            as_of=SEED_CLOCK,
        )
        proposal = _ensure_phase10_proposal(
            conn,
            actor_id=seed_actor,
            data_plane=assembly.data_plane,
            recipient=args.recipient,
            create=not args.no_create,
        )
        manifest = build_manifest(
            conn,
            actor_id=seed_actor,
            proposal=proposal,
            data_plane=assembly.data_plane,
            data_plane_mode=assembly.mode,
            env=live_env,
            ledger_dir=ledger_dir,
        )

    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(_summary(manifest, output_path), indent=2, sort_keys=True))
    return 0


def build_manifest(
    conn,
    *,
    actor_id: str,
    proposal: ActionProposal,
    data_plane,
    data_plane_mode: str,
    env: Mapping[str, str],
    ledger_dir: Path,
) -> dict[str, Any]:
    pending = _pending_phase10_candidates(conn, actor_id=actor_id)
    if len(pending) != 1:
        raise Phase10PrepError(
            f"expected exactly one pending Phase 10 burner candidate, found {len(pending)}"
        )
    if pending[0].proposal_id != proposal.proposal_id:
        raise Phase10PrepError("selected proposal is not the unique pending Phase 10 candidate")

    payload = proposal.payload
    recipient = _recipient(payload)
    if recipient not in RECIPIENT_ALLOWLIST:
        raise Phase10PrepError("selected recipient is not in the hard-coded burner allowlist")
    if not _consent_ok(payload, data_plane):
        raise Phase10PrepError("selected proposal contact does not have consent in the served data plane")
    if canonical_payload_sha256(payload) != proposal.payload_sha256:
        raise Phase10PrepError("payload hash mismatch before approval")

    missing_env = [name for name in REQUIRED_GMAIL_ENV if not env.get(name)]
    sender = env.get("ULTRA_CSM_GMAIL_SENDER", "")
    if missing_env:
        raise Phase10PrepError(
            "missing Gmail committer env names: " + ", ".join(missing_env)
        )

    gate = ActionGate(
        conn,
        tenant_id=TENANT_ID,
        actor_principal_id=actor_id,
        verdict_source=FixtureVerdictSource(),
        now=SEED_CLOCK,
    )
    dry_outcome = GateOutcome(
        proposal_id=proposal.proposal_id,
        status="approved",
        authorized=True,
        payload=payload,
        payload_sha256=proposal.payload_sha256,
        verdict="approve",
    )
    before_count = ledger_send_count(ledger_dir / "gmail_writeback_ledger.jsonl")
    receipt = LiveGmailOutboundCommitter(
        gate,
        env=env,
        ledger_dir=ledger_dir,
        sender=sender,
    ).commit(proposal, dry_outcome, recipient=recipient, dry_run=True)
    after_count = ledger_send_count(ledger_dir / "gmail_writeback_ledger.jsonl")
    if after_count != before_count:
        raise Phase10PrepError("dry-run committer changed live send count")

    approval_command = (
        "PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli proposals approve "
        f"{shlex.quote(proposal.proposal_id)} "
        "--reason 'Owner OA-2 approval for Phase 10 burner send' "
        '--api-token "$ULTRA_CSM_API_TOKEN" '
        "--api-url http://127.0.0.1:8000"
    )
    return {
        "phase": 10,
        "status": "STOP_OWNER_APPROVAL_REQUIRED",
        "owner_action": "OA-2",
        "claim_boundary": {
            "proposal_pending": True,
            "owner_verdict_recorded": False,
            "gmail_send_performed": False,
            "dry_run_only": True,
        },
        "proposal": {
            "proposal_id": proposal.proposal_id,
            "action": proposal.action,
            "status": proposal.status,
            "payload_sha256": proposal.payload_sha256,
            "payload_recomputed_sha256": canonical_payload_sha256(payload),
            "recipient_sha256": _sha256_text(recipient),
            "subject_sha256": _sha256_text(str(payload.get("subject") or "")),
            "body_sha256": _sha256_text(str(payload.get("body") or "")),
            "phase10_marker": bool(payload.get(PHASE10_MARKER)),
        },
        "guards": {
            "unique_pending_phase10_allowlisted_candidate": len(pending) == 1,
            "recipient_allowlisted": recipient in RECIPIENT_ALLOWLIST,
            "recipient_allowlist_size": len(RECIPIENT_ALLOWLIST),
            "contact_consent_in_served_data_plane": True,
            "payload_hash_bound": True,
            "gmail_env_names_present": sorted(REQUIRED_GMAIL_ENV),
            "sender_matches_allowlist": sender in RECIPIENT_ALLOWLIST,
            "data_plane_mode": data_plane_mode,
            "dry_run_receipt": asdict(receipt),
            "ledger_send_count_before": before_count,
            "ledger_send_count_after": after_count,
        },
        "owner_approval": {
            "surface": "REST CLI after the API is running with persistent DB env and live creds loaded",
            "server_env_required": [
                "ULTRA_CSM_DATABASE_URL",
                "ULTRA_CSM_DATABASE_ADMIN_URL",
                "ULTRA_CSM_API_TOKENS",
            ],
            "client_env_required": ["ULTRA_CSM_API_TOKEN"],
            "command_template": approval_command,
            "agent_must_not_run": True,
        },
    }


def _ensure_phase10_actor(conn) -> str:
    with session(conn, tenant_id=TENANT_ID, actor_id=SEED_AGENT, now=SEED_CLOCK) as cur:
        cur.execute(
            "INSERT INTO tenant (tenant_id, name) VALUES (%s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (TENANT_ID, TENANT_NAME),
        )
        cur.execute(
            "INSERT INTO principal (principal_id, tenant_id, kind, display_name) "
            "VALUES (%s, %s, 'agent', %s) ON CONFLICT (principal_id) DO NOTHING",
            (SEED_AGENT, TENANT_ID, "system-seed"),
        )
    seed_roster(conn, tenant_id=TENANT_ID, actor_id=SEED_AGENT, now=SEED_CLOCK)
    return make_principal(
        conn,
        tenant_id=TENANT_ID,
        actor_id=SEED_AGENT,
        display_name="cs-orchestrator",
        role=ROLE_CS_ORCHESTRATOR,
        now=SEED_CLOCK,
    )


def _ensure_phase10_proposal(
    conn,
    *,
    actor_id: str,
    data_plane,
    recipient: str,
    create: bool,
) -> ActionProposal:
    existing = _pending_phase10_candidates(conn, actor_id=actor_id)
    if len(existing) == 1:
        return existing[0]
    if len(existing) > 1:
        raise Phase10PrepError(
            f"multiple pending Phase 10 candidates already exist: {len(existing)}"
        )
    if not create:
        raise Phase10PrepError("no pending Phase 10 candidate exists and --no-create was set")

    account, contact = _choose_consent_contact(data_plane)
    gate = ActionGate(
        conn,
        tenant_id=TENANT_ID,
        actor_principal_id=actor_id,
        verdict_source=FixtureVerdictSource(),
        now=SEED_CLOCK,
    )
    gate.record_outreach_contact_ref(
        account_ref=account.account_id,
        contact_ref=contact.contact_id,
        email=contact.email,
        name=contact.name,
        consent=contact.consent_to_contact,
        cause_ref="phase10:prep:contact-consent",
    )
    payload = {
        "account_id": account.account_id,
        "contact_id": contact.contact_id,
        "contact_email": recipient,
        "subject": f"Phase 10 closed-loop burner outreach for {account.name}",
        "body": (
            "Phase 10 closed-loop validation only. This message is routed to "
            "the owner-controlled burner recipient and must not be sent until "
            "the owner records OA-2 approval."
        ),
        "draft_channel": "email",
        "evidence_ids": [
            f"phase10:served-data-plane:{account.account_id}",
            f"phase10:consent-contact:{contact.contact_id}",
        ],
        PHASE10_MARKER: True,
        "recipient_scope": "burner_allowlist_only",
        "served_contact_email_sha256": _sha256_text(contact.email),
    }
    return gate.propose(
        intent="phase10_close_loop_burner",
        action="draft_customer_outreach",
        payload=payload,
        autonomy_tier=2,
        required_permission="customer.outreach.draft",
        grounding_ref="phase10:burner-send-prep",
        cause_ref="phase10:prep:proposal",
    )


def _pending_phase10_candidates(conn, *, actor_id: str) -> list[ActionProposal]:
    with session(conn, tenant_id=TENANT_ID, actor_id=actor_id, now=SEED_CLOCK) as cur:
        cur.execute(
            "SELECT proposal_id, intent, action, payload, payload_sha256, "
            "autonomy_tier, required_permission, status "
            "FROM action_proposal "
            "WHERE status = 'pending' "
            "  AND action = 'draft_customer_outreach' "
            "  AND payload ->> %s = 'true' "
            "ORDER BY created_ts ASC, proposal_id ASC",
            (PHASE10_MARKER,),
        )
        rows = cur.fetchall()
    return [
        ActionProposal(
            proposal_id=str(row[0]),
            intent=str(row[1]),
            action=str(row[2]),
            payload=dict(row[3]),
            payload_sha256=str(row[4]),
            autonomy_tier=int(row[5]),
            required_permission=str(row[6]),
            status=str(row[7]),
        )
        for row in rows
        if _recipient(dict(row[3])) in RECIPIENT_ALLOWLIST
    ]


def _choose_consent_contact(data_plane):
    for account in data_plane.crm.list_accounts(tenant_id=DEFAULT_TENANT):
        for contact in data_plane.crm.list_contacts(account.account_id):
            if contact.consent_to_contact:
                return account, contact
    raise Phase10PrepError("served data plane has no consented contact")


def _consent_ok(payload: Mapping[str, Any], data_plane) -> bool:
    account_id = payload.get("account_id")
    contact_id = payload.get("contact_id")
    if not isinstance(account_id, str) or not isinstance(contact_id, str):
        return False
    return any(
        contact.contact_id == contact_id and contact.consent_to_contact
        for contact in data_plane.crm.list_contacts(account_id)
    )


def _recipient(payload: Mapping[str, Any]) -> str:
    for key in ("contact_email", "to", "email"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for key, value in dotenv_values(path).items():
        if key and value is not None and key not in os.environ:
            os.environ[key] = value


def _merged_env(creds_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    if creds_path.exists():
        for key, value in dotenv_values(creds_path).items():
            if key and value is not None:
                env[key] = value
    return env


def _summary(manifest: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    proposal = manifest["proposal"]
    guards = manifest["guards"]
    return {
        "manifest": str(output_path),
        "status": manifest["status"],
        "proposal_id": proposal["proposal_id"],
        "payload_sha256": proposal["payload_sha256"],
        "guards_passed": all(
            bool(guards[key])
            for key in (
                "unique_pending_phase10_allowlisted_candidate",
                "recipient_allowlisted",
                "contact_consent_in_served_data_plane",
                "payload_hash_bound",
                "sender_matches_allowlist",
            )
        ),
        "gmail_send_performed": manifest["claim_boundary"]["gmail_send_performed"],
        "owner_action": manifest["owner_action"],
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--operating-env",
        type=Path,
        default=DEFAULT_OPERATING_ENV,
        help="dotenv file with persistent DB URLs",
    )
    parser.add_argument(
        "--creds-env",
        type=Path,
        default=DEFAULT_CREDS_ENV,
        help="dotenv file with Gmail OAuth names",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RUNS_ROOT / "phase10",
        help="out-of-repo artifact directory",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--ledger-dir", type=Path, default=None)
    parser.add_argument(
        "--recipient",
        default=next(iter(sorted(RECIPIENT_ALLOWLIST))),
        choices=sorted(RECIPIENT_ALLOWLIST),
    )
    parser.add_argument("--no-create", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
