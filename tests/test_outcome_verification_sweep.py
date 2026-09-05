"""Outcome verification follows the seeded sweep and its approval boundary."""

from dataclasses import asdict, replace
from datetime import date, timedelta

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1.slot_b import FixtureReasonDraftWriter
from ultra_csm.agent1.sweep import run_time_to_value_sweep
from ultra_csm.data_plane import CustomerDataPlane, DEFAULT_TENANT
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.fixtures import (
    FixtureCommsConnector, FixtureCRMDataConnector,
    FixtureCSPlatformConnector, FixtureProductTelemetryConnector,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.knowledge import load_playbooks
from ultra_csm.value_model import load_value_model_config

TRAILHEAD = "21830db9-7182-5d97-b22e-d57c4e28f696"


@pytest.fixture
def sweep_conn(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        yield runtime_conn
    finally:
        runtime_conn.rollback()


class UnfoundedWriter:
    model_id = "test-live-writer"

    def write(self, request):
        output = FixtureReasonDraftWriter().write(request)
        if getattr(request, "decision_purpose", None) == "outcome_verification":
            return replace(output, model_id=self.model_id, customer_draft=(
                "Hi Vanessa, your rollout is unsuccessful. Can you confirm how we can rescue it?"
            ))
        return output


class FailingWriter:
    model_id = "test-failing-writer"

    def write(self, request):
        raise RuntimeError("test writer unavailable")


def _sweep(conn, *, variant="original", writer=None):
    data = simulate_book(build_synthetic_book(), day_offset=140)
    if variant == "complete":
        data = replace(data, success_plans=tuple(
            replace(plan, status="complete") if plan.account_id == TRAILHEAD else plan
            for plan in data.success_plans
        ))
    elif variant == "blocker":
        data = replace(data, cases=tuple(
            replace(case, subject="Activation blocked: gateway install cannot proceed")
            if case.account_id == TRAILHEAD else case for case in data.cases
        ))
    elif variant == "no_consent":
        data = replace(data, contacts=tuple(
            replace(contact, consent_to_contact=False) if contact.account_id == TRAILHEAD else contact
            for contact in data.contacts
        ))
    elif variant == "no_plans":
        data = replace(data, success_plans=tuple(
            plan for plan in data.success_plans if plan.account_id != TRAILHEAD
        ))
    orch, _ = setup_roster(conn)
    gate = ActionGate(conn, tenant_id=T1, actor_principal_id=orch,
                      verdict_source=FixtureVerdictSource(), now=CLOCK)
    plane = CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data), cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data), comms=FixtureCommsConnector(data=data),
    )
    kwargs = {} if writer is None else {"reason_draft_writer": writer}
    sweep = run_time_to_value_sweep(
        plane, DEFAULT_TENANT, gate, sweep_principal_id=orch,
        as_of=(date.fromisoformat(SEED_DATE) + timedelta(days=140)).isoformat(),
        playbooks=load_playbooks("fleetops"), value_model_config=load_value_model_config(), **kwargs,
    )
    return next((item for item in sweep.work_items if item.account_id == TRAILHEAD), None)


@pytest.mark.parametrize("mode", ["fixture", "unfounded", "failure"])
def test_trailhead_absence_requests_verification(sweep_conn, mode):
    writer = {"fixture": None, "unfounded": UnfoundedWriter(), "failure": FailingWriter()}[mode]
    item = _sweep(sweep_conn, writer=writer)
    print("SWEEP_SOURCE", run_time_to_value_sweep.__code__.co_filename)
    print("TRAILHEAD_DRAFT", item.customer_draft)
    assert "onboarding risk" not in item.customer_draft.lower()
    assert "activation blocker" not in item.customer_draft.lower()
    assert "unsuccessful" not in item.customer_draft.lower()
    assert "confirm the current status" in item.customer_draft
    assert "success-plan objectives" in item.customer_draft
    assert "outcome verification needed" in item.reason
    assert "20527c0a-8156-5119-934a-4017e19fc39d" in item.reason
    assert item.proposal.status == "pending"
    payload = asdict(item)
    assert payload["work_packet"]["prepared_artifact"]["body"] == item.customer_draft
    if mode != "fixture":
        assert item.draft_mode == "template_fallback"
        assert item.draft_fallback_reason == ("contract_rejected" if mode == "unfounded" else "writer_error")


def test_classified_case_retains_remediation_path(sweep_conn):
    item = _sweep(sweep_conn, variant="blocker")
    factor = next(f for f in item.priority.factors if f.name == "slot_a_case_blocker")
    assert factor.evidence[0].source == "crm"
    assert any(c.classification == "blocker" for c in item.slot_a_classifications)
    assert "outcome verification needed" not in item.reason
    assert "onboarding risk" in item.customer_draft


@pytest.mark.parametrize("variant", ["complete", "no_plans"])
def test_changed_plan_evidence_removes_verification_trigger(sweep_conn, variant):
    item = _sweep(sweep_conn, variant=variant)
    if variant == "no_plans":
        assert item is None
        return
    assert not any(f.name == "usage_outcome_unverified" for f in item.priority.factors)
    assert "outcome verification needed" not in item.reason


def test_verification_never_bypasses_contact_prohibition(sweep_conn):
    item = _sweep(sweep_conn, variant="no_consent")
    assert item.customer_draft is None
    assert item.proposal is None
    assert "outcome verification needed" in item.reason
    assert "Review internally" in item.reason
