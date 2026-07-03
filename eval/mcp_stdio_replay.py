"""Replay the demo-operator and relay flows against live MCP stdio servers."""

from __future__ import annotations

import json
import os
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eval.mcp_relay_demo import _confirmations_from_proposal, _synthetic_foreign_book


async def replay_mcp_stdio() -> dict[str, Any]:
    operator = await _operator_replay()
    relay = await _relay_replay()
    return {
        "operator": operator,
        "relay": relay,
        "ok": (
            operator["access_mode"] == "demo_operator"
            and operator["refusal_codes"] == ["CONSENT_MISSING", "PRECEDENCE_HELD"]
            and relay["records_typed"] == {
                "CRMAccount": 2,
                "CRMContact": 2,
                "CRMOpportunity": 2,
            }
        ),
    }


async def _operator_replay() -> dict[str, Any]:
    env = _server_env()
    env["ULTRA_CSM_DEMO_OPERATOR"] = "1"
    env.pop("ULTRA_CSM_MCP_READONLY", None)
    async with _session(env) as session:
        manifest = await _call(session, "get_tool_manifest")
        briefing = await _call(session, "get_morning_briefing")
        proposals = await _call(session, "list_proposals")
        draft = next(
            proposal for proposal in proposals["proposals"]
            if proposal["action"] == "draft_customer_outreach"
            and proposal["intent"] != "mcp_demo_no_consent_refusal"
        )
        await _call(
            session,
            "get_account_brief",
            {"account_id": draft["payload"]["account_id"]},
        )
        revise = await _call(
            session,
            "submit_verdict",
            {
                "proposal_id": draft["proposal_id"],
                "verdict": "revise",
                "reason": "Tighten before approval.",
                "edit_instruction": "Make this more concise.",
            },
        )
        await _call(
            session,
            "submit_verdict",
            {
                "proposal_id": revise["superseding_proposal_id"],
                "verdict": "approve",
                "reason": "Approve revised simulation draft.",
            },
        )
        after_revision = await _call(session, "list_proposals")
        by_intent = {
            proposal["intent"]: proposal
            for proposal in after_revision["proposals"]
        }
        for intent in ("mcp_demo_no_consent_refusal", "mcp_demo_held_expansion_refusal"):
            await _call(
                session,
                "submit_verdict",
                {
                    "proposal_id": by_intent[intent]["proposal_id"],
                    "verdict": "approve",
                    "reason": "Exercise refusal path.",
                },
            )
        ledger = await _call(session, "get_session_ledger")
    return {
        "access_mode": manifest["access_mode"],
        "headline": briefing["headline"],
        "refusal_codes": [
            event["payload"]["code"]
            for event in ledger["events"]
            if event["event_type"] == "refusal"
        ],
    }


async def _relay_replay() -> dict[str, Any]:
    env = _server_env()
    env.pop("ULTRA_CSM_DEMO_OPERATOR", None)
    env.pop("ULTRA_CSM_MCP_READONLY", None)
    async with _session(env) as session:
        readiness = await _call(session, "report_readiness", {"sources": ["crm", "email"]})
        ingest = await _call(
            session,
            "ingest_book",
            {
                "records": _synthetic_foreign_book(),
                "source_descriptor": {
                    "source_name": "synthetic_learning_market",
                    "object_name": "customers",
                },
                "expected_count": 2,
                "session_id": "relay-stdio",
            },
        )
        confirmations = _confirmations_from_proposal(ingest["mapping_proposal"])
        confirm = await _call(
            session,
            "confirm_book_mappings",
            {
                "confirmations": {"confirmations": confirmations},
                "session_id": ingest["session_id"],
            },
        )
    return {
        "ready": readiness["minimum_viable_book"]["ready"],
        "records_typed": confirm["coverage"]["records_typed"],
        "replay_sha256": confirm["replay_sha256"],
    }


def _server_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    return env


def _session(env: dict[str, str]):
    params = StdioServerParameters(
        command=".venv/bin/python",
        args=["-m", "ultra_csm.mcp_server"],
        env=env,
    )
    return _ClientSessionContext(params)


class _ClientSessionContext:
    def __init__(self, params: StdioServerParameters) -> None:
        self._params = params
        self._stdio_cm = None
        self._session_cm = None
        self._session = None

    async def __aenter__(self) -> ClientSession:
        self._stdio_cm = stdio_client(self._params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        assert self._session_cm is not None and self._stdio_cm is not None
        await self._session_cm.__aexit__(*exc)
        await self._stdio_cm.__aexit__(*exc)


async def _call(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = await session.call_tool(name, arguments or {})
    if result.isError:
        raise RuntimeError(f"{name} returned MCP error: {result.content}")
    text = result.content[0].text
    payload = json.loads(text)
    if isinstance(payload, dict) and payload.get("error"):
        return payload
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name} returned non-object payload")
    return payload


def main() -> int:
    result = anyio.run(replay_mcp_stdio)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
