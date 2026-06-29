"""Agent 1 Time-to-Value path over CustomerDataPlane."""

from __future__ import annotations

import inspect

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import TimeToValueAccelerator
from ultra_csm.data_plane import (
    ACME_LOGISTICS,
    CRMContact,
    CustomerDataPlane,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureCustomerData,
    FixtureProductTelemetryConnector,
    build_fixture_data_plane,
    default_fixture_data,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.platform.db import session

AS_OF = "2026-06-27"


@pytest.fixture
def agent1_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


def test_agent1_builds_evidence_bundle_from_customer_data_plane():
    agent = TimeToValueAccelerator(build_fixture_data_plane())

    evidence = agent.build_evidence(ACME_LOGISTICS, as_of=AS_OF)

    assert evidence is not None
    assert evidence.account.account_id == ACME_LOGISTICS
    assert evidence.contacts
    assert evidence.cases
    assert evidence.opportunities
    assert evidence.company.company_id == ACME_LOGISTICS
    assert evidence.health.band == "yellow"
    assert evidence.ctas
    assert evidence.success_plans
    assert evidence.adoption.adoption_rate == 0.40
    assert evidence.entitlements
    assert evidence.usage_signals
    assert evidence.milestones
    assert {m.milestone for m in evidence.open_milestone_gaps} == {
        "activate_50_percent_of_assets",
        "first_route_optimization_workflow",
    }
    assert set(evidence.evidence_signal_ids) <= {
        s.signal_id for s in evidence.usage_signals
    }


def test_agent1_ttv_gap_proposes_gated_customer_outreach(agent1_conn):
    orch, _authority = setup_roster(agent1_conn)
    gate = ActionGate(
        agent1_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )
    agent = TimeToValueAccelerator(build_fixture_data_plane())

    result = agent.propose_customer_outreach(ACME_LOGISTICS, gate, as_of=AS_OF)

    assert result.proposal is not None
    proposal = result.proposal
    assert proposal.status == "pending"
    assert proposal.intent == "agent1_time_to_value"
    assert proposal.action == "draft_customer_outreach"
    assert proposal.autonomy_tier == 2
    assert proposal.required_permission == "customer.outreach.draft"
    assert proposal.payload["evidence"]["crm"]["case_ids"]
    assert proposal.payload["evidence"]["cs_platform"]["cta_ids"]
    assert proposal.payload["evidence"]["telemetry"]["usage_signal_ids"]

    with session(agent1_conn, tenant_id=T1, actor_id=orch, now=CLOCK) as cur:
        cur.execute(
            "SELECT count(*) FROM action_verdict WHERE proposal_id = %s",
            (proposal.proposal_id,),
        )
        assert cur.fetchone()[0] == 0


def test_agent1_ambiguous_identity_escalates_without_proposal(agent1_conn):
    data = default_fixture_data()
    duplicate = CRMContact(
        contact_id="duplicate-contact",
        account_id=data.accounts[1].account_id,
        email=data.contacts[0].email,
        name="Duplicate Contact",
        role="operations",
        title="Ops",
        consent_to_contact=True,
    )
    plane = _plane_with(data, contacts=(*data.contacts, duplicate))
    orch, _authority = setup_roster(agent1_conn)
    gate = ActionGate(
        agent1_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    result = TimeToValueAccelerator(plane).propose_customer_outreach_for_email(
        data.contacts[0].email,
        gate,
        as_of=AS_OF,
    )

    assert result.status == "escalate_identity"
    assert result.proposal is None
    assert _proposal_count(agent1_conn, orch) == 0


def test_agent1_missing_telemetry_blocks_ttv_claim():
    data = default_fixture_data()
    plane = _plane_with(data, milestones=())

    result = TimeToValueAccelerator(plane).recommend(ACME_LOGISTICS, as_of=AS_OF)

    assert result.status == "blocked_missing_telemetry"
    assert result.proposal is None


def test_agent1_blocks_outbound_without_contact_consent(agent1_conn):
    data = default_fixture_data()
    finance = next(c for c in data.contacts if c.email.startswith("finance@"))
    orch, _authority = setup_roster(agent1_conn)
    gate = ActionGate(
        agent1_conn,
        tenant_id=T1,
        actor_principal_id=orch,
        verdict_source=FixtureVerdictSource(),
        now=CLOCK,
    )

    result = TimeToValueAccelerator(build_fixture_data_plane()).propose_customer_outreach(
        ACME_LOGISTICS,
        gate,
        as_of=AS_OF,
        contact_email=finance.email,
    )

    assert result.status == "blocked_contact_consent"
    assert result.contact == finance
    assert result.proposal is None
    assert _proposal_count(agent1_conn, orch) == 0


def test_agent1_import_quarantine():
    import ultra_csm.agent1.time_to_value as module

    source = inspect.getsource(module)
    forbidden = tuple(
        "".join(parts)
        for parts in (
            ("ultra_csm.", "crm"),
            ("CRM", "Connector"),
            ("Stub", "CRM", "Connector"),
            ("tenant", "_directory"),
            ("Domain", "Service"),
            ("eval.", "harness"),
            ("eval.", "catch"),
        )
    )
    assert not any(term in source for term in forbidden)


def _plane_with(data: FixtureCustomerData, **replacements) -> CustomerDataPlane:
    custom = FixtureCustomerData(
        accounts=replacements.get("accounts", data.accounts),
        companies=replacements.get("companies", data.companies),
        contacts=replacements.get("contacts", data.contacts),
        cases=replacements.get("cases", data.cases),
        opportunities=replacements.get("opportunities", data.opportunities),
        health_scores=replacements.get("health_scores", data.health_scores),
        ctas=replacements.get("ctas", data.ctas),
        success_plans=replacements.get("success_plans", data.success_plans),
        adoption_summaries=replacements.get(
            "adoption_summaries",
            data.adoption_summaries,
        ),
        entitlements=replacements.get("entitlements", data.entitlements),
        usage_signals=replacements.get("usage_signals", data.usage_signals),
        milestones=replacements.get("milestones", data.milestones),
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=custom),
        cs=FixtureCSPlatformConnector(data=custom),
        telemetry=FixtureProductTelemetryConnector(data=custom),
    )


def _proposal_count(conn, actor_id: str) -> int:
    with session(conn, tenant_id=T1, actor_id=actor_id, now=CLOCK) as cur:
        cur.execute("SELECT count(*) FROM action_proposal")
        return cur.fetchone()[0]
