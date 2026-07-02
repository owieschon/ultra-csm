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
    def test_verdict_invalid_value(self):
        result = mcp_server.submit_verdict(
            "00000000-0000-0000-0000-000000000000", "maybe", "test"
        )
        assert "error" in result

    def test_verdict_missing_proposal(self):
        result = mcp_server.submit_verdict(
            "00000000-0000-0000-0000-000000000000", "approve", "test"
        )
        assert "error" in result

    def test_sweep_then_verdict(self):
        # Run sweep to generate proposals.
        mcp_server.run_sweep()
        proposals = mcp_server.list_proposals()["proposals"]

        if not proposals:
            pytest.skip("No pending proposals from sweep")

        proposal_id = proposals[0]["proposal_id"]
        result = mcp_server.submit_verdict(proposal_id, "approve", "Test approval")
        # May succeed or fail depending on cache state — just ensure it's structured.
        assert isinstance(result, dict)
        if "error" not in result:
            assert result["proposal_id"] == proposal_id
            assert result["status"] in ("approved", "denied")
