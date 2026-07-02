"""Capture a read-only MCP transcript artifact for the conversational demo."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ultra_csm.data_plane import DEFAULT_DEMO_STATE_DIR
from ultra_csm.data_plane.fixtures import ACME_LOGISTICS

DEFAULT_OUTPUT_PATH = DEFAULT_DEMO_STATE_DIR / "mcp_readonly_transcript.json"


def build_mcp_readonly_transcript(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Run the deterministic read-only demo and write its transcript artifact."""

    os.environ["ULTRA_CSM_MCP_READONLY"] = "1"
    from ultra_csm import mcp_server

    manifest = mcp_server.get_tool_manifest()
    accounts = mcp_server.list_accounts()
    top_accounts = accounts["accounts"][:3]
    acme_hold = mcp_server.get_hold_status(ACME_LOGISTICS)
    acme_trajectory = mcp_server.get_trajectory(ACME_LOGISTICS, window_days=60)
    proposals = mcp_server.list_proposals()
    refused_sweep = mcp_server.run_sweep()
    refused_verdict = mcp_server.submit_verdict(
        "00000000-0000-0000-0000-000000000000",
        "approve",
        "read-only transcript probe",
    )

    questions = (
        {
            "question": "Which accounts need me today and why?",
            "answer": _top_accounts_answer(top_accounts),
            "grounding_tool_calls": [
                _tool_call("list_accounts", {"account_count": accounts["account_count"], "accounts": top_accounts}),
            ],
        },
        {
            "question": "Why is the expansion for Acme Logistics on hold?",
            "answer": _hold_answer(acme_hold),
            "grounding_tool_calls": [
                _tool_call("get_hold_status", acme_hold),
            ],
        },
        {
            "question": "What changed for Acme Logistics in the last 60 days?",
            "answer": _trajectory_answer(acme_trajectory),
            "grounding_tool_calls": [
                _tool_call("get_trajectory", acme_trajectory),
            ],
        },
        {
            "question": "Show me what the agent did autonomously this week.",
            "answer": (
                "Read-only MCP mode found "
                f"{proposals['pending_count']} pending proposals and refused sweep/verdict "
                "write tools, so this transcript records no newly-triggered autonomous work."
            ),
            "grounding_tool_calls": [
                _tool_call("list_proposals", proposals),
                _tool_call("run_sweep", refused_sweep),
                _tool_call("submit_verdict", refused_verdict),
            ],
        },
    )

    artifact = {
        "artifact": "mcp_readonly_transcript",
        "claim_boundary": {"sim": True, "live": False},
        "access_mode": manifest["access_mode"],
        "read_only_env": "ULTRA_CSM_MCP_READONLY",
        "tool_manifest": manifest,
        "questions": list(questions),
    }
    artifact["artifact_sha256"] = _hash_without_self(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _top_accounts_answer(accounts: list[dict[str, Any]]) -> str:
    parts = []
    for account in accounts:
        score = account.get("priority_score")
        band = account.get("health_band", "unknown")
        parts.append(f"{account['account_name']} ({band}, priority {score})")
    return "Top accounts by deterministic priority are: " + "; ".join(parts) + "."


def _hold_answer(status: dict[str, Any]) -> str:
    if status.get("status") == "not_held":
        return f"{status.get('account_name', 'The account')} has no held expansion action."
    blocker_text = ", ".join(blocker["lens"] for blocker in status["blockers"])
    if status.get("status") == "blocked_no_action":
        return (
            f"{status['account_name']} has no customer-facing expansion action in the "
            f"held queue; if one were proposed now, the precedence matrix would block "
            f"it because of active blocker(s): {blocker_text}."
        )
    return (
        f"{status['account_name']}'s customer-facing expansion action is held because "
        f"the precedence matrix found active blocker(s): {blocker_text}. "
        "Findings remain visible; release requires blocker clearance, dismissal, or "
        "authorized override."
    )


def _trajectory_answer(trajectory: dict[str, Any]) -> str:
    points = trajectory.get("points", [])
    if not points:
        return f"{trajectory.get('account_name', 'The account')} has no trajectory points."
    first = points[0]
    last = points[-1]
    return (
        f"{trajectory['account_name']} moved from health score "
        f"{first['health_score']} on day {first['day']} to {last['health_score']} "
        f"on day {last['day']}; trend is {trajectory['trend']}."
    )


def _tool_call(name: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": name,
        "output_sha256": hashlib.sha256(
            json.dumps(output, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "output": output,
    }


def _hash_without_self(artifact: dict[str, Any]) -> str:
    payload = {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def main() -> int:
    artifact = build_mcp_readonly_transcript()
    print(json.dumps({
        "artifact": str(DEFAULT_OUTPUT_PATH),
        "questions": len(artifact["questions"]),
        "access_mode": artifact["access_mode"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
