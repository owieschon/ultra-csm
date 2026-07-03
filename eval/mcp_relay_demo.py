"""Capture the MCP relay-book transcript artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_PATH = Path("eval") / "mcp_relay_transcript.json"


def build_mcp_relay_transcript(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Run the deterministic relay flow and write its transcript artifact."""

    from ultra_csm import mcp_server

    mcp_server._relay_sessions.clear()
    mcp_server._last_relay_session_id = None

    calls: list[dict[str, Any]] = []
    _call(calls, "report_readiness", mcp_server.report_readiness(["crm", "email"]))
    ingest = _call(
        calls,
        "ingest_book",
        mcp_server.ingest_book(
            _synthetic_foreign_book(),
            {"source_name": "synthetic_learning_market", "object_name": "customers"},
            expected_count=2,
            session_id="relay-transcript",
        ),
    )
    confirmations = _confirmations_from_proposal(ingest["mapping_proposal"])
    confirm = _call(
        calls,
        "confirm_book_mappings",
        mcp_server.confirm_book_mappings(
            {"confirmations": confirmations},
            session_id=ingest["session_id"],
        ),
    )
    draft_action = confirm["propose_only_actions"][0]
    approved_proposal = {
        "proposal_id": draft_action["proposal_id"],
        "action": draft_action["action"],
        "status": "approved",
        "payload": draft_action["payload"],
        "payload_sha256": draft_action["payload_sha256"],
    }
    draft = _call(
        calls,
        "render_email_draft",
        mcp_server.render_email_draft(proposal=approved_proposal),
    )
    artifact = {
        "artifact": "mcp_relay_transcript",
        "claim_boundary": {
            "provenance": "mcp_relay",
            "unverified_mapping": True,
            "sim": False,
            "live": False,
        },
        "beats": ["readiness", "ingest", "confirm", "render_email_draft"],
        "session_id": ingest["session_id"],
        "records_typed": confirm["coverage"]["records_typed"],
        "draft_payload_sha256": draft["payload_sha256"],
        "replay_sha256": confirm["replay_sha256"],
        "tool_calls": calls,
    }
    artifact["artifact_sha256"] = _hash_without_self(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _call(calls: list[dict[str, Any]], name: str, output: dict[str, Any]) -> dict[str, Any]:
    calls.append({
        "tool": name,
        "output_sha256": hashlib.sha256(
            json.dumps(output, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "output": output,
    })
    return output


def _synthetic_foreign_book() -> list[dict[str, Any]]:
    return [
        {
            "customer_id": "learning-001",
            "display_name": "Northstar Learning",
            "sector": "education",
            "contacts": [
                {
                    "id": "person-001",
                    "name": "Avery Stone",
                    "email": "avery@example.test",
                    "consent_to_contact": True,
                }
            ],
            "deal_id": "grant-001",
            "arr": "15000",
            "expected_close": "2026-10-15",
        },
        {
            "customer_id": "learning-002",
            "display_name": "Brightpath Academy",
            "sector": "education",
            "contacts": [
                {
                    "id": "person-002",
                    "name": "Riley Park",
                    "email": "riley@example.test",
                    "consent_to_contact": True,
                }
            ],
            "deal_id": "grant-002",
            "arr": "22000",
            "expected_close": "2026-11-01",
        },
    ]


def _confirmations_from_proposal(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    confirmations = {}
    for entry in proposal["entries"]:
        if entry["state"] != "ambiguous_confirm":
            continue
        key = f"{entry['contract']}.{entry['internal_field']}"
        path = {
            "CRMContact.account_id": "customer_id",
            "CRMOpportunity.account_id": "customer_id",
        }.get(key, entry["source_path"])
        value_direction = (
            "higher_is_better"
            if entry["value_direction"] in {"ordered_confirm", "direction_confirm"}
            else "not_applicable"
        )
        confirmations[key] = {
            "contract": entry["contract"],
            "internal_field": entry["internal_field"],
            "source_object": entry["source_object"] or "customers",
            "source_field": (path or entry["source_field"]).rsplit(".", 1)[-1],
            "source_path": path,
            "semantic_role": entry["semantic_role"],
            "value_direction": value_direction,
            "verdict": "mapped",
        }
    return confirmations


def _hash_without_self(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def main() -> int:
    artifact = build_mcp_relay_transcript()
    print(json.dumps({
        "artifact": str(DEFAULT_OUTPUT_PATH),
        "records_typed": artifact["records_typed"],
        "tool_calls": len(artifact["tool_calls"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
