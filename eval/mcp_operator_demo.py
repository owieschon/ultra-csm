"""Capture the MCP demo-operator transcript artifact."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_PATH = Path("eval") / "mcp_operator_transcript.json"
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def build_mcp_operator_transcript(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Run the deterministic operator demo and write its transcript artifact."""

    os.environ["ULTRA_CSM_DEMO_OPERATOR"] = "1"
    os.environ.pop("ULTRA_CSM_MCP_READONLY", None)
    from ultra_csm import mcp_server

    calls: list[dict[str, Any]] = []
    stable_ids: dict[str, str] = {}

    manifest = _call(calls, "get_tool_manifest", mcp_server.get_tool_manifest(), stable_ids)
    briefing = _call(calls, "get_morning_briefing", mcp_server.get_morning_briefing(), stable_ids)
    proposals = _call(calls, "list_proposals", mcp_server.list_proposals(), stable_ids)

    draft = _first_operator_draft(proposals["proposals"])
    account_id = str(draft["payload"]["account_id"])
    _call(calls, "get_account_brief", mcp_server.get_account_brief(account_id), stable_ids)

    revise = _call(
        calls,
        "submit_verdict(revise)",
        mcp_server.submit_verdict(
            draft["proposal_id"],
            "revise",
            "Tighten the draft before approval.",
            edit_instruction="Make this more concise.",
        ),
        stable_ids,
    )
    _call(
        calls,
        "submit_verdict(approve)",
        mcp_server.submit_verdict(
            revise["superseding_proposal_id"],
            "approve",
            "Approved revised simulation draft.",
        ),
        stable_ids,
    )

    after_revision = _call(
        calls,
        "list_proposals(after_revision)",
        mcp_server.list_proposals(),
        stable_ids,
    )
    no_consent = _proposal_by_intent(
        after_revision["proposals"],
        "mcp_demo_no_consent_refusal",
    )
    held_expansion = _proposal_by_intent(
        after_revision["proposals"],
        "mcp_demo_held_expansion_refusal",
    )
    _call(
        calls,
        "submit_verdict(no_consent_refusal)",
        mcp_server.submit_verdict(
            no_consent["proposal_id"],
            "approve",
            "Try the no-consent refusal path.",
        ),
        stable_ids,
    )
    _call(
        calls,
        "submit_verdict(held_expansion_refusal)",
        mcp_server.submit_verdict(
            held_expansion["proposal_id"],
            "approve",
            "Try the held-expansion refusal path.",
        ),
        stable_ids,
    )
    ledger = _call(calls, "get_session_ledger", mcp_server.get_session_ledger(), stable_ids)
    _call(calls, "get_next_steps", mcp_server.get_next_steps(), stable_ids)

    artifact = {
        "artifact": "mcp_operator_transcript",
        "claim_boundary": {"sim": True, "live": False},
        "access_mode": manifest["access_mode"],
        "headline": briefing["headline"],
        "beats": [
            "briefing",
            "queue",
            "evidence",
            "revise",
            "approve_with_receipt",
            "refusal",
            "session_receipts",
        ],
        "refusal_codes": [
            event["payload"]["code"]
            for event in ledger["events"]
            if event["event_type"] == "refusal"
        ],
        "tool_calls": calls,
    }
    artifact = _normalized_artifact(artifact)
    artifact["artifact_sha256"] = _hash_without_self(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _call(
    calls: list[dict[str, Any]],
    name: str,
    output: dict[str, Any],
    stable_ids: dict[str, str],
) -> dict[str, Any]:
    normalized = _normalize(output, stable_ids)
    calls.append({
        "tool": name,
        "output_sha256": hashlib.sha256(
            json.dumps(normalized, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "output": normalized,
    })
    return output


def _first_operator_draft(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    drafts = [
        proposal for proposal in proposals
        if proposal["action"] == "draft_customer_outreach"
        and proposal["intent"] != "mcp_demo_no_consent_refusal"
    ]
    return sorted(
        drafts,
        key=lambda item: (
            str(item["payload"].get("account_name", "")),
            str(item["payload"].get("account_id", "")),
        ),
    )[0]


def _proposal_by_intent(proposals: list[dict[str, Any]], intent: str) -> dict[str, Any]:
    return next(proposal for proposal in proposals if proposal["intent"] == intent)


def _normalized_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return _normalize(artifact)


def _normalize(value: Any, ids: dict[str, str] | None = None) -> Any:
    ids = ids if ids is not None else {}
    if isinstance(value, str):
        return UUID_RE.sub(lambda match: _stable_id(match.group(0), ids), value)
    if isinstance(value, list):
        items = [_normalize(item, ids) for item in value]
        if items and all(isinstance(item, dict) and "proposal_id" in item for item in items):
            return sorted(
                items,
                key=lambda item: (
                    str(item.get("intent", "")),
                    str(item.get("action", "")),
                    str(item.get("payload", {}).get("account_name", "")),
                    str(item.get("proposal_id", "")),
                ),
            )
        return items
    if isinstance(value, dict):
        _record_semantic_ids(value, ids)
        normalized = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {"payload_sha256", "approved_payload_sha256"}:
                normalized[key_text] = "<payload-sha256>"
            elif key_text in {"receipt_id", "idempotency_key"} and isinstance(item, str):
                normalized[key_text] = _stable_aux_id(key_text, value, ids)
                ids[item] = normalized[key_text]
            else:
                normalized[key_text] = _normalize(item, ids)
        return normalized
    return value


def _record_semantic_ids(value: dict[str, Any], ids: dict[str, str]) -> None:
    proposal_id = value.get("proposal_id")
    if isinstance(proposal_id, str) and UUID_RE.fullmatch(proposal_id):
        ids[proposal_id] = _semantic_proposal_id(value)
    superseding_id = value.get("superseding_proposal_id")
    if isinstance(superseding_id, str) and UUID_RE.fullmatch(superseding_id):
        ids[superseding_id] = "<proposal:superseding-draft>"


def _semantic_proposal_id(value: dict[str, Any]) -> str:
    intent = str(value.get("intent") or "verdict")
    action = str(value.get("action") or "")
    payload = value.get("payload")
    account = ""
    if isinstance(payload, dict):
        account = str(payload.get("account_name") or payload.get("account_id") or "")
    return "<proposal:" + ":".join(
        part for part in (intent, action, _slug(account)) if part
    ) + ">"


def _stable_aux_id(kind: str, value: dict[str, Any], ids: dict[str, str]) -> str:
    proposal_id = value.get("proposal_id")
    proposal_ref = ids.get(proposal_id, "<proposal:unknown>") if isinstance(proposal_id, str) else "<proposal:unknown>"
    return f"<{kind}:{proposal_ref.strip('<>')}>"


def _stable_id(value: str, ids: dict[str, str]) -> str:
    if value not in ids:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        ids[value] = f"<uuid:{digest}>"
    return ids[value]


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "unknown"


def _hash_without_self(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def main() -> int:
    artifact = build_mcp_operator_transcript()
    print(json.dumps({
        "artifact": str(DEFAULT_OUTPUT_PATH),
        "access_mode": artifact["access_mode"],
        "tool_calls": len(artifact["tool_calls"]),
        "refusal_codes": artifact["refusal_codes"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
