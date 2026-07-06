from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from ultra_csm.data_plane import build_fixture_data_plane

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operating"
    / "prepare_phase10_send.py"
)
_SPEC = importlib.util.spec_from_file_location("phase10_send_prep", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
prep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(prep)


@pytest.fixture
def phase10_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def _env() -> dict[str, str]:
    return {
        "ULTRA_CSM_GMAIL_OAUTH_CLIENT_ID": "client",
        "ULTRA_CSM_GMAIL_OAUTH_CLIENT_SECRET": "secret",
        "ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN": "refresh",
        "ULTRA_CSM_GMAIL_SENDER": "agenticardvarkpug@gmail.com",
    }


def test_phase10_manifest_prepares_unique_pending_burner_candidate_without_send(
    phase10_conn, tmp_path
):
    data_plane = build_fixture_data_plane()
    actor_id = prep._ensure_phase10_actor(phase10_conn)
    proposal = prep._ensure_phase10_proposal(
        phase10_conn,
        actor_id=actor_id,
        data_plane=data_plane,
        recipient="agenticardvarkpug@gmail.com",
        create=True,
    )

    manifest = prep.build_manifest(
        phase10_conn,
        actor_id=actor_id,
        proposal=proposal,
        data_plane=data_plane,
        data_plane_mode="fixture",
        env=_env(),
        ledger_dir=tmp_path,
    )

    assert manifest["status"] == "STOP_OWNER_APPROVAL_REQUIRED"
    assert manifest["claim_boundary"] == {
        "proposal_pending": True,
        "owner_verdict_recorded": False,
        "gmail_send_performed": False,
        "dry_run_only": True,
    }
    assert manifest["guards"]["unique_pending_phase10_allowlisted_candidate"] is True
    assert manifest["guards"]["recipient_allowlisted"] is True
    assert manifest["guards"]["contact_consent_in_served_data_plane"] is True
    assert manifest["guards"]["payload_hash_bound"] is True
    assert manifest["guards"]["dry_run_receipt"]["dry_run"] is True
    assert manifest["guards"]["dry_run_receipt"]["committed"] is True
    assert manifest["guards"]["ledger_send_count_before"] == 0
    assert manifest["guards"]["ledger_send_count_after"] == 0
    assert manifest["owner_approval"]["agent_must_not_run"] is True


def test_phase10_manifest_fails_closed_without_gmail_env_names(phase10_conn, tmp_path):
    data_plane = build_fixture_data_plane()
    actor_id = prep._ensure_phase10_actor(phase10_conn)
    proposal = prep._ensure_phase10_proposal(
        phase10_conn,
        actor_id=actor_id,
        data_plane=data_plane,
        recipient="agenticardvarkpug@gmail.com",
        create=True,
    )

    with pytest.raises(prep.Phase10PrepError, match="missing Gmail committer env names"):
        prep.build_manifest(
            phase10_conn,
            actor_id=actor_id,
            proposal=proposal,
            data_plane=data_plane,
            data_plane_mode="fixture",
            env={},
            ledger_dir=tmp_path,
        )
