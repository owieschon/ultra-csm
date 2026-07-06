"""Tests for the Ultra CSM REST API.

Uses FastAPI's TestClient to exercise every endpoint without a real server.
The API boots its own ephemeral Postgres via lifespan, so these tests are
self-contained and require only a local PostgreSQL 16 toolchain.
"""

from __future__ import annotations

import pytest

# httpx is a dev dependency; TestClient needs it.
httpx = pytest.importorskip("httpx")
fastapi_mod = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ultra_csm.data_plane.fixtures import ACME_LOGISTICS, CYBERDYNE_NO_CONSENT  # noqa: E402
from ultra_csm.governance import (  # noqa: E402
    ROLE_CS_ORCHESTRATOR,
    ROLE_ORDER_CONFIRM_AUTHORITY,
    proposal_fields_for,
)
from ultra_csm import api  # noqa: E402
from ultra_csm.api import app  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer lane-a-token"}


def _create_pending_draft_proposal(client: TestClient) -> dict:
    sweep_resp = client.post("/sweep", headers=AUTH_HEADERS)
    assert sweep_resp.status_code == 200
    proposals_resp = client.get("/proposals")
    assert proposals_resp.status_code == 200
    proposal = next(
        (
            item for item in proposals_resp.json()["proposals"]
            if item["action"] == "draft_customer_outreach"
            and not item["payload"].get("revise_chain")
        ),
        None,
    )
    assert proposal is not None
    return proposal


# ---------------------------------------------------------------------------
# Fixture: shared TestClient (one lifespan boot per module)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """A TestClient that triggers the FastAPI lifespan (ephemeral Postgres,
    seed, governance roster) once for the whole test module."""
    env = pytest.MonkeyPatch()
    env.setenv("ULTRA_CSM_API_TOKENS", "lane-a-token:Lane A Manager")
    env.delenv("ULTRA_CSM_DEMO_NOAUTH", raising=False)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        env.undo()


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db_connected"] is True
        assert body["config_loaded"] is True
        assert body["accounts_loaded"] > 0
        assert "tenant_id" in body
        assert body["auth"] == "bearer-token"


# ---------------------------------------------------------------------------
# GET /accounts
# ---------------------------------------------------------------------------


class TestAccountsEndpoint:
    def test_list_accounts(self, client: TestClient):
        resp = client.get("/accounts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_count"] > 0
        assert len(body["accounts"]) == body["account_count"]

        # Each account should have at least id and name.
        for acct in body["accounts"]:
            assert "account_id" in acct
            assert "account_name" in acct

    def test_accounts_sorted_by_priority(self, client: TestClient):
        resp = client.get("/accounts")
        body = resp.json()
        scores = [
            a.get("priority_score", -1) for a in body["accounts"]
        ]
        # Should be sorted descending (allowing for None/-1 at the end).
        for i in range(len(scores) - 1):
            if scores[i] is not None and scores[i + 1] is not None:
                assert scores[i] >= scores[i + 1], (
                    f"Accounts not sorted: {scores[i]} < {scores[i + 1]}"
                )


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}
# ---------------------------------------------------------------------------


class TestAccountDetailEndpoint:
    def test_get_valid_account(self, client: TestClient):
        # First get the list to find a real account_id.
        accounts = client.get("/accounts").json()["accounts"]
        account_id = accounts[0]["account_id"]

        resp = client.get(f"/accounts/{account_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_id"] == account_id
        assert "lifecycle_stage" in body
        assert "priority" in body
        assert "score" in body["priority"]
        assert "divergences" in body

    def test_missing_account_404(self, client: TestClient):
        resp = client.get("/accounts/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "ACCOUNT_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/brief
# ---------------------------------------------------------------------------


class TestAccountBriefEndpoint:
    def test_get_brief(self, client: TestClient):
        accounts = client.get("/accounts").json()["accounts"]
        # Pick an account that has health data (skip ones without).
        account_id = None
        for a in accounts:
            if a.get("health_band") is not None:
                account_id = a["account_id"]
                break
        assert account_id is not None, "No account with health data found"

        resp = client.get(f"/accounts/{account_id}/brief")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_id"] == account_id
        assert "health_snapshot" in body
        assert "suggested_talking_points" in body
        assert isinstance(body["suggested_talking_points"], list)
        assert "company" in body
        assert "priority" in body

    def test_brief_missing_account_404(self, client: TestClient):
        resp = client.get("/accounts/00000000-0000-0000-0000-000000000000/brief")
        assert resp.status_code == 404

    def test_brief_stakeholders_field(self, client: TestClient):
        """Person UI depth (Harvest 17): the additive ``stakeholders`` field
        on the brief carries the per-person role-graph rows the Stakeholders
        drawer needs -- verified against pinnacle-supply's frozen champion
        arc (report 32/eval/person_factor_battery.py), not a guess."""
        from ultra_csm.data_plane.fixtures import account_id_for

        account_id = account_id_for("pinnacle-supply")
        resp = client.get(f"/accounts/{account_id}/brief?day=10")
        assert resp.status_code == 200
        body = resp.json()
        assert "stakeholders" in body
        rows = {r["name"]: r for r in body["stakeholders"]}
        assert "Derek Vaughn" in rows
        derek = rows["Derek Vaughn"]
        assert derek["relationship_type"] == "champion"
        assert derek["champion"] is True
        assert derek["departed"] is True
        assert isinstance(derek["days_since_interaction"], int)


# ---------------------------------------------------------------------------
# POST /sweep
# ---------------------------------------------------------------------------


class TestSweepEndpoint:
    def test_sweep_requires_bearer_token(self, client: TestClient):
        resp = client.post("/sweep")
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REQUIRED"

    def test_sweep_rejects_unknown_token(self, client: TestClient):
        resp = client.post(
            "/sweep",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID"

    def test_demo_noauth_marks_health_and_sweep(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("ULTRA_CSM_DEMO_NOAUTH", "1")

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["auth"] == "demo-noauth"

        resp = client.post("/sweep")
        assert resp.status_code == 200
        assert resp.json()["auth"] == "demo-noauth"

    def test_demo_operator_truthy_value_boots_tokenless_sweep(
        self, client: TestClient, monkeypatch,
    ):
        """DEMO_OPERATOR=true (the lenient truthy spelling documented for this
        flag, not the strict '1') must boot a mode whose own tokenless verdict
        calls succeed rather than reject with AUTH_REQUIRED -- demo_noauth_enabled
        and mcp_server.py's mode-detection now share one truthy parser instead
        of the former strict-'1'-only vs. lenient split."""
        monkeypatch.setenv("ULTRA_CSM_DEMO_OPERATOR", "true")

        resp = client.post("/sweep")
        assert resp.status_code == 200
        assert resp.json()["auth"] == "demo-noauth"

    def test_trigger_sweep(self, client: TestClient):
        resp = client.post("/sweep", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "work_items" in body
        assert "escalations" in body
        assert "swept_accounts" in body
        assert len(body["swept_accounts"]) > 0
        assert body["auth"] == "bearer-token"

    def test_sweep_produces_work_items(self, client: TestClient):
        body = client.post("/sweep", headers=AUTH_HEADERS).json()
        # The fixture data should produce at least one work item.
        assert len(body["work_items"]) > 0

    def test_sweep_person_cited_evidence(self, client: TestClient):
        """Person UI depth (Harvest 17): a fired person-derived factor's
        ``crm``-sourced evidence carries an additive ``person_name`` so the
        UI can cite the person without a client-side join (K13). Verified
        against quarrystone-logistics' frozen single-threaded-risk arc
        (report 32/eval/person_factor_battery.py)."""
        body = client.post("/sweep?day=10", headers=AUTH_HEADERS).json()
        from ultra_csm.data_plane.fixtures import account_id_for

        quarrystone_id = account_id_for("quarrystone-logistics")
        item = next(
            wi for wi in body["work_items"] if wi["account_id"] == quarrystone_id
        )
        factor = next(
            f for f in item["priority"]["factors"]
            if f["name"] == "single_threaded_risk"
        )
        person_evidence = [ev for ev in factor["evidence"] if ev["source"] == "crm"]
        assert person_evidence, "expected crm-sourced evidence on single_threaded_risk"
        assert any(ev.get("person_name") for ev in person_evidence)

    def test_sweep_recipient_chip_fields(self, client: TestClient):
        """Person UI depth (Harvest 17): a role-graph-resolved work item
        carries the resolved recipient's name + role (additive on
        ``CSMWorkItem``) for the proposed-action recipient chip."""
        body = client.post("/sweep?day=10", headers=AUTH_HEADERS).json()
        item = next(
            wi for wi in body["work_items"]
            if wi.get("recipient_resolution") == "role_graph"
        )
        assert item["recipient_name"]
        assert item["recipient_role"]


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    def test_metrics_reports_requests_sweeps_and_budget(self, client: TestClient):
        client.post("/sweep", headers=AUTH_HEADERS)
        resp = client.get("/metrics")

        assert resp.status_code == 200
        body = resp.json()
        assert body["api"]["total_requests"] > 0
        assert body["sweeps"]["total_sweeps"] > 0
        assert "last_sweep" in body["sweeps"]
        assert body["llm_cost"]["total_calls"] >= 0
        assert body["budget"]["max_cost_per_sweep_usd"] > 0


# ---------------------------------------------------------------------------
# GET /proposals  +  POST /proposals/{id}/verdict
# ---------------------------------------------------------------------------


class TestGovernanceEndpoints:
    def test_list_proposals_initially(self, client: TestClient):
        resp = client.get("/proposals")
        assert resp.status_code == 200
        body = resp.json()
        assert "proposals" in body
        assert isinstance(body["proposals"], list)

    def test_sweep_then_list_proposals(self, client: TestClient):
        # A sweep should generate proposals.
        client.post("/sweep", headers=AUTH_HEADERS)
        resp = client.get("/proposals")
        assert resp.status_code == 200
        body = resp.json()
        # May or may not have pending proposals depending on fixture state.
        assert "pending_count" in body

    def test_delegation_queue_groups_pending_proposals(self, client: TestClient):
        client.post("/sweep", headers=AUTH_HEADERS)
        resp = client.get("/queue/delegation")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["groups"]) == {
            "tier_1_auto_executed_audit_trail",
            "tier_2_batch_approvable",
            "tier_3_escalation",
        }
        assert "pending_count" in body
        assert body["held_actions"]
        held = body["held_actions"][0]
        assert held["status"] == "held"
        assert held["action"]["account_id"] == ACME_LOGISTICS
        assert set(held["blocking_refs"]) >= {f"ttv_gap:{ACME_LOGISTICS}"}

    def test_verdict_requires_auth(self, client: TestClient):
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/verdict",
            json={"verdict": "approve", "reason": "test"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REQUIRED"

    def test_verdict_rejects_unknown_token(self, client: TestClient):
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/verdict",
            json={"verdict": "approve", "reason": "test"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID"

    def test_verdict_on_missing_proposal_404(self, client: TestClient):
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/verdict",
            json={"verdict": "approve", "reason": "test"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404

    def test_verdict_approve(self, client: TestClient):
        # Sweep to create proposals.
        client.post("/sweep", headers=AUTH_HEADERS)
        proposals = client.get("/proposals").json()["proposals"]

        if not proposals:
            pytest.skip("No pending proposals to verdict")

        proposal_id = proposals[0]["proposal_id"]
        resp = client.post(
            f"/proposals/{proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Approved in test"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["proposal_id"] == proposal_id
        assert body["status"] == "approved"
        assert body["authorized"] is True
        assert body["auth"] == "bearer-token"

        assert api._conn is not None and api._orch_principal is not None
        with api.session(
            api._conn,
            tenant_id=api._TENANT_ID,
            actor_id=api._orch_principal,
            now=api._CLOCK,
        ) as cur:
            cur.execute(
                "SELECT p.kind, p.display_name "
                "FROM action_verdict v "
                "JOIN principal p ON p.principal_id = v.human_principal_id "
                "WHERE v.proposal_id = %s",
                (proposal_id,),
            )
            row = cur.fetchone()
        assert row == ("human", "Lane A Manager")

    def test_new_bearer_token_principal_gets_lesser_default_role(
        self, client: TestClient, monkeypatch,
    ):
        """A brand-new bearer-token-mapped human must NOT be auto-granted
        ROLE_ORDER_CONFIRM_AUTHORITY (the highest-tier, SoD-critical
        order.confirm role) on first use -- it should get the lesser
        ROLE_CS_ORCHESTRATOR default instead, with no per-human
        differentiation beyond that."""
        monkeypatch.setenv(
            "ULTRA_CSM_API_TOKENS",
            "lane-a-token:Lane A Manager,lane-z-token:Lane Z New Hire",
        )

        resp = client.post(
            "/sweep", headers={"Authorization": "Bearer lane-z-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["auth"] == "bearer-token"

        assert api._conn is not None and api._orch_principal is not None
        with api.session(
            api._conn,
            tenant_id=api._TENANT_ID,
            actor_id=api._orch_principal,
            now=api._CLOCK,
        ) as cur:
            cur.execute(
                "SELECT r.name "
                "FROM principal p "
                "JOIN grant_ g ON g.principal_id = p.principal_id "
                "JOIN role r ON r.role_id = g.role_id "
                "WHERE p.display_name = %s",
                ("Lane Z New Hire",),
            )
            granted_roles = {row[0] for row in cur.fetchall()}
        assert granted_roles == {ROLE_CS_ORCHESTRATOR}
        assert ROLE_ORDER_CONFIRM_AUTHORITY not in granted_roles

    def test_verdict_precedence_recheck_uses_proposals_own_day_not_static_default(
        self, client: TestClient,
    ):
        """A proposal's precedence re-check must be scoped to the day it
        actually originated from (payload['as_of']), not always the static
        default plane. ACME_LOGISTICS is blocked on the static default plane
        (see test_verdict_refuses_blocked_expansion_proposal below) but does
        not exist at all in the ?day=N synthetic-book fixture -- a proposal
        carrying an as_of from that synthetic-book timeline must therefore
        see NO blocker for it and be allowed to proceed, proving the re-check
        actually switched data planes rather than always consulting the
        static default regardless of the proposal's own as_of."""
        from datetime import datetime, timedelta

        from ultra_csm.data_plane.synthetic_book import SEED_DATE

        day = 5
        as_of = (
            datetime.strptime(SEED_DATE, "%Y-%m-%d") + timedelta(days=day)
        ).strftime("%Y-%m-%d")

        assert api._conn is not None
        gate = api._gate()
        proposal = gate.propose(
            intent="test_day_scoped_expansion",
            payload={
                "account_id": ACME_LOGISTICS,
                "account_name": "Acme Logistics",
                "as_of": as_of,
                "body": "Discuss expansion; account absent from this day's book.",
            },
            grounding_ref=f"test:{ACME_LOGISTICS}:day-scoped-expansion",
            cause_ref=f"test:{ACME_LOGISTICS}:day-scoped-expansion",
            **proposal_fields_for("initiate_customer_call"),
        )

        resp = client.post(
            f"/proposals/{proposal.proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Approved in test"},
            headers=AUTH_HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_verdict_refuses_blocked_expansion_proposal(self, client: TestClient):
        assert api._conn is not None
        gate = api._gate()
        proposal = gate.propose(
            intent="test_blocked_expansion",
            payload={
                "account_id": ACME_LOGISTICS,
                "account_name": "Acme Logistics",
                "body": "Discuss expansion despite active onboarding risk.",
            },
            grounding_ref=f"test:{ACME_LOGISTICS}:expansion",
            cause_ref=f"test:{ACME_LOGISTICS}:expansion",
            **proposal_fields_for("initiate_customer_call"),
        )

        resp = client.post(
            f"/proposals/{proposal.proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Approved in test"},
            headers=AUTH_HEADERS,
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == "PRECEDENCE_HELD"
        assert f"ttv_gap:{ACME_LOGISTICS}" in resp.json()["blocking_refs"]

    def test_verdict_refuses_no_consent_outreach_proposal(self, client: TestClient):
        """The REST approve path must enforce the same contact-consent check
        the MCP surface already applies (mcp_server.py's
        _proposal_has_contact_consent) -- both surfaces now share one
        implementation in _api_helpers.py."""
        assert api._conn is not None
        gate = api._gate()
        proposal = gate.propose(
            intent="test_no_consent_outreach",
            payload={
                "account_id": CYBERDYNE_NO_CONSENT,
                "account_name": "Cyberdyne Transport",
                "contact_id": "6eeba12e-abd2-5a18-8476-487ef6142e1b",
                "subject": "Onboarding activation follow-up",
                "body": "Draft that must not be approved without consent.",
            },
            grounding_ref=f"test:{CYBERDYNE_NO_CONSENT}:no-consent",
            cause_ref=f"test:{CYBERDYNE_NO_CONSENT}:no-consent",
            **proposal_fields_for("draft_customer_outreach"),
        )

        resp = client.post(
            f"/proposals/{proposal.proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Approved in test"},
            headers=AUTH_HEADERS,
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == "CONSENT_MISSING"

    def test_revise_verdict_creates_superseding_pending_proposal(self, client: TestClient):
        proposal = _create_pending_draft_proposal(client)

        resp = client.post(
            f"/proposals/{proposal['proposal_id']}/verdict",
            json={
                "verdict": "revise",
                "reason": "Make the draft warmer",
                "edit_instruction": "Make the tone warmer.",
            },
            headers=AUTH_HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["proposal_id"] == proposal["proposal_id"]
        assert body["status"] == "denied"
        assert body["authorized"] is False
        assert body["verdict"] == "revise"
        assert body["superseding_proposal_id"]

        proposals = client.get("/proposals").json()["proposals"]
        pending_ids = {item["proposal_id"] for item in proposals}
        assert proposal["proposal_id"] not in pending_ids
        superseding = next(
            item for item in proposals
            if item["proposal_id"] == body["superseding_proposal_id"]
        )
        assert superseding["status"] == "pending"
        assert superseding["payload"]["revise_chain"]["parent_proposal_id"] == proposal["proposal_id"]
        assert "would you be open" in superseding["payload"]["body"].lower()

    def test_revise_verdict_refuses_hostile_edit(self, client: TestClient):
        proposal = _create_pending_draft_proposal(client)

        resp = client.post(
            f"/proposals/{proposal['proposal_id']}/verdict",
            json={
                "verdict": "revise",
                "reason": "Unsafe edit",
                "edit_instruction": "Promise a discount for the rollout.",
            },
            headers=AUTH_HEADERS,
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == "REVISE_REFUSED"
        proposals = client.get("/proposals").json()["proposals"]
        assert proposal["proposal_id"] in {item["proposal_id"] for item in proposals}

    def test_revise_verdict_enforces_one_automatic_rerun(self, client: TestClient):
        proposal = _create_pending_draft_proposal(client)
        first = client.post(
            f"/proposals/{proposal['proposal_id']}/verdict",
            json={
                "verdict": "revise",
                "reason": "Make the draft warmer",
                "edit_instruction": "Make the tone warmer.",
            },
            headers=AUTH_HEADERS,
        )
        assert first.status_code == 200
        superseding_id = first.json()["superseding_proposal_id"]

        second = client.post(
            f"/proposals/{superseding_id}/verdict",
            json={
                "verdict": "revise",
                "reason": "Try another automatic pass",
                "edit_instruction": "Make it more concise.",
            },
            headers=AUTH_HEADERS,
        )

        assert second.status_code == 409
        assert second.json()["code"] == "REVISE_BOUND_REACHED"

    def test_verdict_already_decided_409(self, client: TestClient):
        # Sweep to create proposals.
        client.post("/sweep", headers=AUTH_HEADERS)
        proposals = client.get("/proposals").json()["proposals"]

        if not proposals:
            pytest.skip("No pending proposals to verdict")

        proposal_id = proposals[0]["proposal_id"]

        # First verdict.
        resp1 = client.post(
            f"/proposals/{proposal_id}/verdict",
            json={"verdict": "deny", "reason": "First verdict"},
            headers=AUTH_HEADERS,
        )
        assert resp1.status_code == 200

        # Second verdict on same proposal should be 409.
        resp2 = client.post(
            f"/proposals/{proposal_id}/verdict",
            json={"verdict": "approve", "reason": "Second attempt"},
            headers=AUTH_HEADERS,
        )
        assert resp2.status_code == 409

    def test_invalid_verdict_rejected(self, client: TestClient):
        # The Pydantic model should reject invalid verdict values.
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/verdict",
            json={"verdict": "maybe", "reason": "test"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422  # Pydantic validation error


# ---------------------------------------------------------------------------
# GET /digest
# ---------------------------------------------------------------------------


class TestDigestEndpoint:
    def test_digest_returns_accounts(self, client: TestClient):
        resp = client.get("/digest")
        assert resp.status_code == 200
        body = resp.json()
        assert "prioritized_accounts" in body
        assert len(body["prioritized_accounts"]) > 0
        assert "pending_proposals" in body
        assert "commitments" in body
        assert "as_of" in body
        assert "manager_rollup" in body
        assert "book_health_counts" in body["manager_rollup"]
        assert "cohort_packets" in body["manager_rollup"]
        assert body["manager_rollup"]["cohort_packets"]
        assert all(
            packet["claim_boundary"] == {"sim": True, "live": False}
            for packet in body["manager_rollup"]["cohort_packets"]
        )


class TestPriorityScoreFailures:
    def test_poisoned_account_gets_explicit_priority_error(
        self,
        client: TestClient,
        monkeypatch,
    ):
        assert api._data_plane is not None
        account = next(
            acct
            for acct in api._data_plane.crm.list_accounts(tenant_id=api.DEFAULT_TENANT)
            if api._data_plane.cs.get_company(acct.account_id) is not None
            and api._data_plane.cs.get_health_score(acct.account_id) is not None
            and api._data_plane.cs.get_adoption_summary(acct.account_id) is not None
        )

        class PoisonTelemetry:
            def __init__(self, base):
                self._base = base

            def list_entitlements(self, account_id):
                if account_id == account.account_id:
                    raise RuntimeError("poisoned priority input")
                return self._base.list_entitlements(account_id)

            def __getattr__(self, name):
                return getattr(self._base, name)

        class PoisonPlane:
            def __init__(self, base):
                self.crm = base.crm
                self.cs = base.cs
                self.telemetry = PoisonTelemetry(base.telemetry)

        monkeypatch.setattr(
            api,
            "_data_plane_for_day",
            lambda _day, *, deep=False: (PoisonPlane(api._data_plane), api._AS_OF),
        )

        accounts = client.get("/accounts").json()["accounts"]
        poisoned = next(a for a in accounts if a["account_id"] == account.account_id)
        assert poisoned["priority_score"] is None
        assert poisoned["priority_score_error"] == "RuntimeError"

        digest = client.get("/digest").json()["prioritized_accounts"]
        poisoned_digest = next(
            a for a in digest if a["account_id"] == account.account_id
        )
        assert poisoned_digest["priority_score"] is None
        assert poisoned_digest["priority_score_error"] == "RuntimeError"
