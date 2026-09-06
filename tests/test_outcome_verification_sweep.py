"""Outcome verification follows the seeded sweep and its approval boundary."""

from dataclasses import asdict, replace
from datetime import date, timedelta

import pytest

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1.slot_b import FixtureReasonDraftWriter
from ultra_csm.agent1.sweep import build_reason_draft_request_for_account, run_time_to_value_sweep
from ultra_csm.data_plane import CustomerDataPlane, DEFAULT_TENANT
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.contracts import (
    AdoptionSummary, CRMAccount, CRMContact, CSCompany, HealthScore, SuccessPlan,
)
from ultra_csm.data_plane.fixtures import (
    FixtureCommsConnector, FixtureCRMDataConnector, FixtureCSPlatformConnector,
    FixtureCustomerData, FixtureProductTelemetryConnector, det_id,
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


# ---------------------------------------------------------------------------
# Evidence-gap regression: an active (not-yet-overdue) objective plus high
# adoption is the only relevant fact for these accounts -- no overdue plan,
# open CTA, open case, or grounded overdue milestone. Before this fix,
# `_slot_b_inputs_for_account` returned None from an empty base evidence
# tuple before `build_customer_value_model` ever ran, silently dropping the
# account even though the usage_outcome_unverified factor it would have
# produced carries its own cited evidence (active_users + the objective's
# own plan-objective/status refs).
# ---------------------------------------------------------------------------

GAP_AS_OF = "2026-06-21"
GAP_FUTURE_TARGET = "2026-08-15"  # after GAP_AS_OF: not overdue


def _gap_company(account_id: str, slug: str, *, arr_cents: int = 8_000_000) -> CSCompany:
    return CSCompany(
        company_id=account_id,
        name=slug.replace("-", " ").title(),
        industry="logistics",
        arr_cents=arr_cents,
        lifecycle_stage="adopting",
        status="Active",
        original_contract_date="2026-01-01",
        renewal_date="2027-01-01",
        csm_owner_id="csm-gap",
        current_score=82.0,
    )


def _gap_contact(account_id: str, slug: str, *, consent: bool = True) -> CRMContact:
    return CRMContact(
        contact_id=det_id("gap-evidence-contact", account_id, slug),
        account_id=account_id,
        email=f"{slug}@{slug}.example",
        name=slug.replace("-", " ").title(),
        role="operations",
        title="VP Operations",
        consent_to_contact=consent,
    )


def _gap_scenario(
    slug: str,
    *,
    objectives: tuple[str, ...],
    active_users: int,
    licensed_users: int,
    plan_status: str = "in_progress",
    consent: bool = True,
) -> tuple[CRMAccount, CSCompany, CRMContact, HealthScore, AdoptionSummary, tuple[SuccessPlan, ...]]:
    account_id = det_id("gap-evidence-account", slug)
    account = CRMAccount(account_id=account_id, name=slug, owner_id="csm-gap", industry="logistics")
    company = _gap_company(account_id, slug)
    contact = _gap_contact(account_id, slug, consent=consent)
    health = HealthScore(
        account_id=account_id, score=82.0, band="green", drivers=(), measured_at=GAP_AS_OF,
    )
    adoption = AdoptionSummary(
        account_id=account_id, active_users=active_users, licensed_users=licensed_users,
        active_assets=active_users, entitled_assets=licensed_users,
        adoption_rate=active_users / licensed_users, underused_capabilities=(), measured_at=GAP_AS_OF,
    )
    plans = ()
    if objectives:
        plans = (SuccessPlan(
            plan_id=det_id("gap-evidence-plan", slug), account_id=account_id, status=plan_status,
            objectives=objectives, target_date=GAP_FUTURE_TARGET,
        ),)
    return account, company, contact, health, adoption, plans


GAP_SCENARIOS = {
    "technical_activation": _gap_scenario(
        "gap-tech-activation", objectives=("technical product activation",),
        active_users=18, licensed_users=20,
    ),
    "enterprise_onboarding": _gap_scenario(
        "gap-enterprise-onboarding", objectives=("enterprise onboarding",),
        active_users=18, licensed_users=20,
    ),
    "complete_plan": _gap_scenario(
        "gap-complete-plan", objectives=("technical product activation",),
        active_users=18, licensed_users=20, plan_status="complete",
    ),
    "no_objectives": _gap_scenario(
        "gap-no-objectives", objectives=(), active_users=18, licensed_users=20,
    ),
    "low_activity": _gap_scenario(
        "gap-low-activity", objectives=("technical product activation",),
        active_users=4, licensed_users=20,
    ),
    "unrelated_noise": _gap_scenario(
        "gap-unrelated-noise", objectives=(), active_users=3, licensed_users=20,
    ),
    "no_consent": _gap_scenario(
        "gap-no-consent", objectives=("technical product activation",),
        active_users=18, licensed_users=20, consent=False,
    ),
}


def _gap_data() -> FixtureCustomerData:
    accounts, companies, contacts, health_scores, adoption_summaries = [], [], [], [], []
    plans: list[SuccessPlan] = []
    for account, company, contact, health, adoption, account_plans in GAP_SCENARIOS.values():
        accounts.append(account)
        companies.append(company)
        contacts.append(contact)
        health_scores.append(health)
        adoption_summaries.append(adoption)
        plans.extend(account_plans)
    return FixtureCustomerData(
        accounts=tuple(accounts),
        companies=tuple(companies),
        contacts=tuple(contacts),
        cases=(),
        opportunities=(),
        health_scores=tuple(health_scores),
        ctas=(),
        success_plans=tuple(plans),
        adoption_summaries=tuple(adoption_summaries),
        entitlements=(),
        usage_signals=(),
        milestones=(),
    )


def _gap_sweep(conn):
    data = _gap_data()
    orch, _ = setup_roster(conn)
    gate = ActionGate(conn, tenant_id=T1, actor_principal_id=orch,
                      verdict_source=FixtureVerdictSource(), now=CLOCK)
    plane = CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=data), cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data), comms=FixtureCommsConnector(data=data),
    )
    sweep = run_time_to_value_sweep(
        plane, DEFAULT_TENANT, gate, sweep_principal_id=orch,
        as_of=GAP_AS_OF, value_model_config=load_value_model_config(),
    )
    return plane, {item.account_id: item for item in sweep.work_items}


@pytest.mark.parametrize("scenario", ["technical_activation", "enterprise_onboarding"])
def test_active_objective_with_high_adoption_is_not_dropped(sweep_conn, scenario):
    """An unresolved objective plus high adoption -- with no overdue plan,
    open CTA, open case, or grounded overdue milestone -- must still surface
    a pending outcome-verification proposal instead of vanishing from the
    sweep."""

    account_id = GAP_SCENARIOS[scenario][0].account_id
    _, items = _gap_sweep(sweep_conn)
    item = items.get(account_id)
    assert item is not None, f"{scenario} account was dropped before the value model ran"
    factor_names = {f.name for f in item.priority.factors}
    assert "usage_outcome_unverified" in factor_names
    assert "outcome verification needed" in item.reason
    assert item.proposal is not None
    assert item.proposal.status == "pending"
    assert item.customer_draft is not None
    assert "onboarding risk" not in item.customer_draft.lower()
    assert "activation blocker" not in item.customer_draft.lower()


@pytest.mark.parametrize("scenario", ["complete_plan", "no_objectives", "low_activity", "unrelated_noise"])
def test_positive_controls_do_not_acquire_verification(sweep_conn, scenario):
    account_id = GAP_SCENARIOS[scenario][0].account_id
    _, items = _gap_sweep(sweep_conn)
    assert items.get(account_id) is None


def test_no_consent_keeps_internal_review_without_customer_draft(sweep_conn):
    account_id = GAP_SCENARIOS["no_consent"][0].account_id
    _, items = _gap_sweep(sweep_conn)
    item = items.get(account_id)
    assert item is not None
    assert item.customer_draft is None
    assert item.proposal is None
    assert "outcome verification needed" in item.reason
    assert "Review internally" in item.reason


def test_request_reconstruction_cites_objective_and_adoption_evidence(sweep_conn):
    account, *_ = GAP_SCENARIOS["technical_activation"]
    plane, _ = _gap_sweep(sweep_conn)

    full_request = build_reason_draft_request_for_account(
        plane, DEFAULT_TENANT, account.account_id, as_of=GAP_AS_OF,
    )
    assert full_request is not None
    source_ids = {ev.source_id for ev in full_request.evidence}
    assert account.account_id in source_ids  # active_users evidence
    plan_id = GAP_SCENARIOS["technical_activation"][5][0].plan_id
    assert plan_id in source_ids  # plan objectives/status evidence

    restricted = build_reason_draft_request_for_account(
        plane, DEFAULT_TENANT, account.account_id, as_of=GAP_AS_OF,
        evidence_source_ids=(account.account_id, plan_id),
    )
    assert restricted is not None
    assert {ev.source_id for ev in restricted.evidence} == {account.account_id, plan_id}

    unmatched = build_reason_draft_request_for_account(
        plane, DEFAULT_TENANT, account.account_id, as_of=GAP_AS_OF,
        evidence_source_ids=("not-a-real-source-id",),
    )
    assert unmatched is None
