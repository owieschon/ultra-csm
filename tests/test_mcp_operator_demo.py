"""Tests for the MCP demo-operator transcript."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_operator_transcript_is_deterministic(tmp_path):
    first = tmp_path / "first.json"
    repo = Path.cwd()

    _run_operator_transcript()
    artifact = repo / "eval" / "mcp_operator_transcript.json"
    first.write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")

    _run_operator_transcript()
    second = artifact.read_text(encoding="utf-8")

    assert first.read_text(encoding="utf-8") == second
    data = json.loads(second)
    assert data["access_mode"] == "demo_operator"
    assert data["claim_boundary"] == {"sim": True, "live": False}
    assert data["refusal_codes"] == ["CONSENT_MISSING", "PRECEDENCE_HELD"]
    assert "approve_with_receipt" in data["beats"]
    assert "render_email_draft" in data["beats"]


def test_relay_transcript_is_deterministic(tmp_path):
    first = tmp_path / "first-relay.json"
    repo = Path.cwd()

    _run_relay_transcript()
    artifact = repo / "eval" / "mcp_relay_transcript.json"
    first.write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")

    _run_relay_transcript()
    second = artifact.read_text(encoding="utf-8")

    assert first.read_text(encoding="utf-8") == second
    data = json.loads(second)
    assert data["claim_boundary"] == {
        "provenance": "mcp_relay",
        "unverified_mapping": True,
        "sim": False,
        "live": False,
    }
    assert data["records_typed"]["CRMAccount"] == 2
    assert data["records_typed"]["CRMContact"] == 2
    assert "render_email_draft" in data["beats"]
    assert len(data["draft_payload_sha256"]) == 64


def test_operator_and_readonly_modes_are_mutually_exclusive():
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    env["ULTRA_CSM_DEMO_OPERATOR"] = "1"
    env["ULTRA_CSM_MCP_READONLY"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", "from ultra_csm import mcp_server"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "mutually exclusive" in result.stderr


def _run_operator_transcript() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    env["ULTRA_CSM_DEMO_OPERATOR"] = "1"
    env.pop("ULTRA_CSM_MCP_READONLY", None)
    subprocess.run(
        [sys.executable, "-m", "eval.mcp_operator_demo"],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_relay_transcript() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    env.pop("ULTRA_CSM_MCP_READONLY", None)
    env.pop("ULTRA_CSM_DEMO_OPERATOR", None)
    subprocess.run(
        [sys.executable, "-m", "eval.mcp_relay_demo"],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
