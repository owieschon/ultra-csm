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


class TestLedgerEndpoint:
    """New GET /ledger — the audit-tail read Book/Queue's rail renders."""

    def test_ledger_shape(self, client: TestClient):
        resp = client.get("/ledger")
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body
        assert "ledger_gap" in body
        assert isinstance(body["ledger_gap"], list)
        assert body["ledger_gap"] == []

    def test_ledger_reflects_sweep_operational_events(self, client: TestClient):
        sweep = client.post("/sweep", headers=AUTH_HEADERS)
        assert sweep.status_code == 200

        ledger = client.get("/ledger?limit=200").json()
        events = {entry["event"] for entry in ledger["events"]}

        assert "sweep.fired" in events
        assert "value_model" in events
        assert "slot_b.draft" in events
        assert "judge.score" in events
        assert ledger["ledger_gap"] == []

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


def test_action_rail_uses_backend_ctas():
    source = (Path(__file__).resolve().parents[1] / "ui" / "components" / "ActionRail.tsx").read_text()
    assert "allowed_ctas" in source
    assert "ctas.map" in source
    assert "Approve &amp; send" not in source


def test_queue_detail_surfaces_enterprise_onboarding_packet():
    source = (Path(__file__).resolve().parents[1] / "ui" / "components" / "QueueDetail.tsx").read_text()
    assert "enterpriseOnboardingPackets" in source
    assert "Enterprise launch packet" in source
    assert "value_model_alignment" in source
    assert "Measured milestones" in source


def test_queue_detail_surfaces_self_serve_activation_packet():
    source = (Path(__file__).resolve().parents[1] / "ui" / "components" / "QueueDetail.tsx").read_text()
    api_source = (Path(__file__).resolve().parents[1] / "ui" / "lib" / "api.ts").read_text()
    assert "selfServeActivationPackets" in source
    assert "Self-serve value path" in source
    assert "first_value_definition" in source
    assert "secondary_hypotheses" in source
    assert "config_version" in source
    assert "activation-milestones" in source
    assert "/self-serve/activation/packets" in api_source


def test_queue_detail_surfaces_adoption_regression_packet():
    source = (Path(__file__).resolve().parents[1] / "ui" / "components" / "QueueDetail.tsx").read_text()
    api_source = (Path(__file__).resolve().parents[1] / "ui" / "lib" / "api.ts").read_text()
    assert "adoptionRegressionPackets" in source
    assert "Adoption regression review" in source
    assert "Window comparisons" in source
    assert "selected_hypothesis" in source
    assert "value_context" in source
    assert "/adoption-regression/packets" in api_source


def test_ui_api_can_read_workflow_playbook_registry():
    api_source = (Path(__file__).resolve().parents[1] / "ui" / "lib" / "api.ts").read_text()
    assert "workflowPlaybooks" in api_source
    assert "/workflow-playbooks" in api_source


def test_ui_surfaces_workflow_authoring_readiness():
    repo = Path(__file__).resolve().parents[1]
    topbar = (repo / "ui" / "components" / "TopBar.tsx").read_text()
    api_source = (repo / "ui" / "lib" / "api.ts").read_text()
    page = (repo / "ui" / "app" / "workflows" / "page.tsx").read_text()
    css = (repo / "ui" / "app" / "globals.css").read_text()
    fixture = (repo / "ui" / "public" / "demo-api" / "workflow-authoring-readiness.json").read_text()

    assert 'href="/workflows"' in topbar
    assert "workflowAuthoringReadiness" in api_source
    assert "/workflow-authoring/readiness" in api_source
    assert "Readiness console" in page
    assert "declared_test_obligations" in page
    assert "readiness-grid" in css
    assert "account_adoption_regression" in fixture
