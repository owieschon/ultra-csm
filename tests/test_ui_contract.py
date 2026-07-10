"""API contract tests for the operations-surface UI (Harvest 9, report 27).

Every field the Next.js UI in `ui/` consumes is asserted here — not
pixel-correctness, just "the field exists with the right shape." Mirrors
test_api.py's TestClient/fixture conventions exactly (no second pattern).
"""

from __future__ import annotations

from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.api import app  # noqa: E402
from ultra_csm.action_control_contract import ActionControlVerticalSlice  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer lane-a-token"}


@pytest.fixture(scope="module")
def client():
    env = pytest.MonkeyPatch()
    env.setenv("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
    env.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        env.undo()


class TestAccountsTierField:
    """Book view's tier bands need `tier` on every /accounts row."""

    def test_accounts_carry_tier(self, client: TestClient):
        resp = client.get("/accounts")
        assert resp.status_code == 200
        accounts = resp.json()["accounts"]
        assert accounts
        tiers = {a.get("tier") for a in accounts}
        assert tiers, "no account resolved a tier at all"
        assert tiers <= {"high_touch", "mid_touch", "tech_touch"}

    def test_accounts_tier_present_for_every_account_with_company_data(
        self, client: TestClient
    ):
        resp = client.get("/accounts")
        accounts = resp.json()["accounts"]
        with_lifecycle = [a for a in accounts if a.get("lifecycle_stage")]
        assert with_lifecycle
        for account in with_lifecycle:
            assert account["tier"] is not None, account["account_id"]


class TestSweepMotionLive:
    """Queue view's motion chip and cohort rows need real (non-null)
    `motion` values from /sweep, not the opt-in-but-unused state report 23
    left behind."""

    def test_sweep_work_items_carry_motion(self, client: TestClient):
        resp = client.post("/sweep", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        work_items = resp.json()["work_items"]
        assert work_items
        with_account = [
            item for item in work_items if item.get("account_id") is not None
        ]
        assert with_account, "no per-account work items in this sweep"
        motions = {item.get("motion") for item in with_account}
        assert motions != {None}, "motion resolution not live on /sweep"

    def test_sweep_cohort_collapse_present(self, client: TestClient):
        resp = client.post("/sweep", headers=AUTH_HEADERS)
        work_items = resp.json()["work_items"]
        cohort_items = [
            item for item in work_items if item.get("account_id") is None
            and item.get("candidate_account_ids")
        ]
        # Cohort collapse is data-dependent (needs >= threshold same
        # tier+trigger accounts); assert the FIELD SHAPE is right whether or
        # not the fixture book happens to produce one this sweep.
        for item in cohort_items:
            assert isinstance(item["candidate_account_ids"], list)
            assert len(item["candidate_account_ids"]) >= 1

    def test_sweep_work_items_carry_work_packet(self, client: TestClient):
        resp = client.post("/sweep", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        work_items = resp.json()["work_items"]
        assert work_items
        packet = work_items[0].get("work_packet")
        assert packet is not None
        assert packet["packet_version"] == "csm-work-packet-v1"
        assert packet["allowed_ctas"]
        assert packet["governance_boundary"]["source_organ"] == "governance.csm_actions"
        assert packet["diagnostic_hypothesis"]["label"] == "unverified_hypothesis"


class TestLedgerEndpoint:
    """New GET /ledger — the audit-tail read Book/Queue's rail renders."""

    def test_ledger_shape(self, client: TestClient):
        resp = client.get("/ledger")
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body
        assert "ledger_gap" in body
        assert isinstance(body["ledger_gap"], list)
        assert {"gmail.commit", "reobserve.queue"} <= set(body["ledger_gap"])

    def test_ledger_reflects_sweep_operational_events(self, client: TestClient):
        sweep = client.post("/sweep", headers=AUTH_HEADERS)
        assert sweep.status_code == 200

        ledger = client.get("/ledger?limit=200").json()
        events = {entry["event"] for entry in ledger["events"]}

        assert "sweep.fired" in events
        assert "value_model" in events
        assert "slot_b.draft" in events
        assert "judge.score" in events
        # Handoff-lane and self-serve events are registered but do not fire in a
        # default fixture sweep; the self-serve trio fires in its own workflow
        # context (tests/test_self_serve_*), so listing it here is truthful.
        assert set(ledger["ledger_gap"]) == {
            "gmail.commit",
            "reobserve.queue",
            "self_serve_activation.trigger",
            "self_serve_activation.packet",
            "self_serve_activation.value_path",
        }

    def test_ledger_reflects_a_real_verdict(self, client: TestClient):
        client.post("/sweep", headers=AUTH_HEADERS)
        proposals = client.get("/proposals").json()["proposals"]
        proposal = next(
            (p for p in proposals if p["action"] == "draft_customer_outreach"),
            None,
        )
        assert proposal is not None, "sweep is expected to yield a draft_customer_outreach proposal"
        verdict_resp = client.post(
            f"/proposals/{proposal['proposal_id']}/verdict",
            headers=AUTH_HEADERS,
            json={"verdict": "deny", "reason": "ui contract test"},
        )
        assert verdict_resp.status_code == 200

        ledger = client.get("/ledger").json()
        matching = [
            e for e in ledger["events"]
            if e["proposal_id"] == proposal["proposal_id"]
        ]
        events = {e["event"] for e in matching}
        assert "gate.propose" in events
        assert "gate.deny" in events
        for entry in matching:
            assert entry["label"], entry
            assert entry["ts"], entry

    def test_ledger_event_names_are_two_register(self, client: TestClient):
        """UI_DESIGN_BRIEF's two-register rule: `label` is plain English,
        `event` carries the raw enum for the mono/tooltip receipt."""
        resp = client.get("/ledger")
        for entry in resp.json()["events"]:
            assert entry["label"] != entry["event"] or entry["event"] not in {
                "gate.propose", "gate.approve", "gate.deny", "gate.revise",
            }


class TestCorsConfigured:
    def test_cors_preflight_allows_localhost_3000(self, client: TestClient):
        resp = client.options(
            "/accounts",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


class TestActionControlVerticalSlice:
    def test_contract_endpoint_exposes_approved_receipt_and_tamper_refusal(
        self, client: TestClient
    ):
        response = client.get("/demo/action-control/vertical-slice")

        assert response.status_code == 200
        contract = ActionControlVerticalSlice.model_validate(response.json())
        assert contract.schema_version == "action-control.vertical-slice.v1"
        assert contract.state_sequence == (
            "pending_human_decision",
            "approved_payload_bound",
            "simulated_committed",
            "refused_payload_mismatch",
        )
        assert contract.simulated_receipt.external_effect is False
        assert contract.tamper_refusal.code == "PAYLOAD_HASH_MISMATCH"


class TestActionControlSandbox:
    def test_sandbox_starts_without_login_and_never_enables_outbound_effects(
        self, client: TestClient
    ):
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": "6492863b-0e9b-4a63-bb53-ee54c86bc29c",
                "expected_state_sha256": None,
                "commands": [],
            },
        )

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["state"] == "pending_human_decision"
        assert payload["outbound_effects_enabled"] is False
        assert payload["isolation"]["database_transaction"] == "rolled_back"

    def test_sandbox_validation_is_non_reflective_on_the_main_api(
        self, client: TestClient
    ):
        private_draft = "PRIVATE-MAIN-API-DRAFT-SENTINEL-" + "x" * 800
        response = client.post(
            "/demo/action-control/sandbox/evaluate",
            json={
                "schema_version": "action-control.sandbox-command-log.v1",
                "run_id": "92c43d9a-92ec-4b9f-a022-ad66f0334a48",
                "expected_state_sha256": "0" * 64,
                "commands": [
                    {
                        "command_id": "ad5329f6-2b36-4ab4-9a33-e93d2df8e616",
                        "type": "revise_and_approve",
                        "draft": private_draft,
                    }
                ],
            },
        )

        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "detail": {
                "code": "INVALID_SANDBOX_REQUEST",
                "fields": ["commands.0.draft"],
            }
        }
        assert "PRIVATE-MAIN-API-DRAFT-SENTINEL" not in response.text

    def test_ui_never_calls_approved_work_sent_and_typing_disables_shortcuts(self):
        root = Path(__file__).resolve().parents[1]
        action_rail = (root / "ui" / "components" / "ActionRail.tsx").read_text()
        queue_lanes = (root / "ui" / "components" / "QueueLanes.tsx").read_text()
        book_view = (root / "ui" / "components" / "BookView.tsx").read_text()
        shortcuts = (root / "ui" / "components" / "ShortcutsOverlay.tsx").read_text()
        labels = (root / "ui" / "lib" / "labels.ts").read_text()
        page = (root / "ui" / "app" / "page.tsx").read_text()

        assert "Approve &amp; send" not in action_rail
        assert "Approve & send" not in shortcuts
        assert '? "sent"' not in queue_lanes
        assert ': "sent"' not in book_view
        assert 'approved: "approved · sent"' not in labels
        assert 'target.matches("input, textarea, select")' in page
        assert "target.isContentEditable" in page
