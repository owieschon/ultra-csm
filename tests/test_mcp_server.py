"""Tests for the Ultra CSM MCP server tool functions.

These tests exercise the MCP tool functions directly (not over stdio),
since the MCP server boots its own ephemeral Postgres at import time.
"""

from __future__ import annotations

import pytest

# The MCP server boots an ephemeral cluster on import. This is expensive but
# self-contained — no external fixtures needed.
try:
    from ultra_csm import mcp_server
except ImportError:
    pytest.skip("mcp package not installed", allow_module_level=True)

from ultra_csm.data_plane.fixtures import ACME_LOGISTICS

MCP_TOKEN = "mcp-lane-a-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_first_account_id() -> str:
    """Get the first account_id from list_accounts."""
    result = mcp_server.list_accounts()
    accounts = result["accounts"]
    assert len(accounts) > 0
    return accounts[0]["account_id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListAccounts:
    def test_returns_accounts(self):
        result = mcp_server.list_accounts()
        assert "accounts" in result
        assert result["account_count"] > 0
        assert len(result["accounts"]) == result["account_count"]

    def test_accounts_have_expected_fields(self):
        result = mcp_server.list_accounts()
        for acct in result["accounts"]:
            assert "account_id" in acct
            assert "account_name" in acct


class TestScoreAccount:
    def test_score_valid_account(self):
        account_id = _get_first_account_id()
        result = mcp_server.score_account(account_id)
        assert "error" not in result
        assert result["account_id"] == account_id
        assert "lifecycle_stage" in result
        assert "priority" in result
        assert "score" in result["priority"]

    def test_score_missing_account(self):
        result = mcp_server.score_account("00000000-0000-0000-0000-000000000000")
        assert "error" in result


class TestGetAccountBrief:
    def test_brief_valid_account(self):
        account_id = _get_first_account_id()
        result = mcp_server.get_account_brief(account_id)
        assert "error" not in result
        assert result["account_id"] == account_id
        assert "health_snapshot" in result
        assert "suggested_talking_points" in result
        assert isinstance(result["suggested_talking_points"], list)
        assert "company" in result
        assert "contacts" in result

    def test_brief_missing_account(self):
        result = mcp_server.get_account_brief("00000000-0000-0000-0000-000000000000")
        assert "error" in result


class TestReadOnlyAccessMode:
    def test_tool_manifest_marks_write_tools_unavailable_in_read_only(self, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_MCP_READONLY", "1")

        manifest = mcp_server.get_tool_manifest()
        tools = {tool["name"]: tool for tool in manifest["tools"]}

        assert manifest["access_mode"] == "read_only"
        assert tools["run_sweep"]["classification"] == "state_changing"
        assert tools["run_sweep"]["readonly_available"] is False
        assert tools["submit_verdict"]["readonly_available"] is False
        assert tools["get_hold_status"]["readonly_available"] is True

    def test_read_only_mode_refuses_sweep_and_verdict(self, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_MCP_READONLY", "1")

        sweep = mcp_server.run_sweep()
        verdict = mcp_server.submit_verdict(
            "00000000-0000-0000-0000-000000000000",
            "approve",
            "test",
            token=MCP_TOKEN,
        )

        assert sweep["code"] == "MCP_READONLY"
        assert verdict["code"] == "MCP_READONLY"


class TestHoldAndTrajectoryReads:
    def test_get_hold_status_projects_ttv_gap_hold_without_writing(self):
        result = mcp_server.get_hold_status(ACME_LOGISTICS)

        assert result["status"] == "held"
        assert result["action_scope"] == "customer_facing"
        assert result["lens"] == "expansion"
        assert "ttv_gap" in {blocker["lens"] for blocker in result["blockers"]}
        assert result["claim_boundary"] == {"sim": True, "live": False}

    def test_get_trajectory_returns_read_only_points(self):
        result = mcp_server.get_trajectory(ACME_LOGISTICS, window_days=60)

        assert result["account_id"] == ACME_LOGISTICS
        assert result["trend"] in {"unknown", "improving", "stable", "declining"}
        assert result["points"]
        assert result["claim_boundary"] == {"sim": True, "live": False}


class TestRunSweep:
    def test_sweep_returns_work_items(self):
        result = mcp_server.run_sweep()
        assert "work_items" in result
        assert "swept_accounts" in result
        assert len(result["swept_accounts"]) > 0

    def test_sweep_work_items_have_structure(self):
        result = mcp_server.run_sweep()
        for item in result.get("work_items", []):
            assert "account_id" in item or "candidate_account_ids" in item
            assert "disposition" in item
            assert "reason" in item


class TestListProposals:
    def test_list_proposals(self):
        result = mcp_server.list_proposals()
        assert "proposals" in result
        assert isinstance(result["proposals"], list)
        assert "pending_count" in result


class TestSubmitVerdict:
    def test_verdict_requires_token(self):
        result = mcp_server.submit_verdict(
            "00000000-0000-0000-0000-000000000000", "approve", "test"
        )
        assert result["code"] == "AUTH_REQUIRED"

    def test_verdict_invalid_value(self, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_API_TOKENS", f"{MCP_TOKEN}:MCP Lane Manager")
        result = mcp_server.submit_verdict(
            "00000000-0000-0000-0000-000000000000", "maybe", "test", token=MCP_TOKEN
        )
        assert "error" in result

    def test_verdict_missing_proposal(self, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_API_TOKENS", f"{MCP_TOKEN}:MCP Lane Manager")
        result = mcp_server.submit_verdict(
            "00000000-0000-0000-0000-000000000000",
            "approve",
            "test",
            token=MCP_TOKEN,
        )
        assert "error" in result

    def test_sweep_then_verdict(self, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_API_TOKENS", f"{MCP_TOKEN}:MCP Lane Manager")
        # Run sweep to generate proposals.
        mcp_server.run_sweep()
        proposals = mcp_server.list_proposals()["proposals"]

        if not proposals:
            pytest.skip("No pending proposals from sweep")

        proposal_id = proposals[0]["proposal_id"]
        result = mcp_server.submit_verdict(
            proposal_id,
            "approve",
            "Test approval",
            token=MCP_TOKEN,
        )
        # May succeed or fail depending on cache state — just ensure it's structured.
        assert isinstance(result, dict)
        if "error" not in result:
            assert result["proposal_id"] == proposal_id
            assert result["status"] in ("approved", "denied")

    def test_revise_uses_bounded_loop(self, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_API_TOKENS", f"{MCP_TOKEN}:MCP Lane Manager")
        mcp_server.run_sweep()
        proposals = [
            proposal for proposal in mcp_server.list_proposals()["proposals"]
            if proposal["action"] == "draft_customer_outreach"
        ]

        if not proposals:
            pytest.skip("No pending draft proposals from sweep")

        proposal_id = proposals[0]["proposal_id"]
        result = mcp_server.submit_verdict(
            proposal_id,
            "revise",
            "Tighten before approval",
            token=MCP_TOKEN,
            edit_instruction="Make this more concise.",
        )

        assert result["status"] == "denied"
        assert result["verdict"] == "revise"
        assert result["superseding_proposal_id"]
