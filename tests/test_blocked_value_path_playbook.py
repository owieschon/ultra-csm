from __future__ import annotations

from types import SimpleNamespace

from tests._govhelpers import CLOCK, T1, setup_roster
from ultra_csm.agent1 import run_time_to_value_sweep
from ultra_csm.blocked_value_path import assess_blocked_value_path
from ultra_csm.data_plane import ACME_LOGISTICS, DEFAULT_TENANT, build_sweep_fixture_data_plane
from ultra_csm.data_plane.contracts import (
    AdoptionSummary,
    CommunicationSignal,
    CRMAccount,
    CRMCase,
    CRMContact,
    CSCompany,
    CTA,
    Entitlement,
    HealthScore,
    InternalCommsNote,
    OnboardingPhase,
    OnboardingProject,
    OnboardingTask,
    StakeholderRelationship,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.governance import ActionGate, FixtureVerdictSource
from ultra_csm.work_packets import PacketInputs, build_work_packet, planned_customer_draft


AS_OF = "2026-07-28"


def test_blocked_value_path_requires_and_records_full_source_coverage():
    packet_inputs = _pinehill_like_packet_inputs()

    assessment = assess_blocked_value_path(
        account=packet_inputs.account,
        as_of=packet_inputs.as_of,
        cases=packet_inputs.cases,
        success_plans=packet_inputs.success_plans,
        usage_signals=packet_inputs.usage_signals,
        milestones=packet_inputs.milestones,
        contacts=packet_inputs.contacts,
        selected_contact=packet_inputs.selected_contact,
        priority_factors=packet_inputs.priority_factors,
        adoption=packet_inputs.adoption,
        entitlements=packet_inputs.entitlements,
        stakeholders=packet_inputs.stakeholders,
        company=packet_inputs.company,
        health=packet_inputs.health,
        ctas=packet_inputs.ctas,
        communication_signals=packet_inputs.communication_signals,
        internal_notes=packet_inputs.internal_notes,
        onboarding_projects=packet_inputs.onboarding_projects,
        onboarding_phases=packet_inputs.onboarding_phases,
        onboarding_tasks=packet_inputs.onboarding_tasks,
    )

    assert assessment.triggered is True
    assert assessment.missing_required_sources == ()
    assert set(assessment.original_plan_sources) == {
        "cs_company",
        "success_plan",
        "entitlements",
        "ttv_milestones",
        "onboarding_project_plan",
    }
    assert set(assessment.current_state_sources) == {
        "crm_cases",
        "cs_ctas",
        "health_score",
        "adoption_summary",
        "product_usage",
        "customer_comms",
        "internal_notes",
        "relationship_graph",
    }
    assert "legacy dispatch integration" == assessment.blocking_dependency
    assert "route optimization workflow" == assessment.blocked_workflow


def test_work_packet_customer_output_is_recovery_not_generic_adoption():
    packet = build_work_packet(_pinehill_like_packet_inputs())
    rendered = " ".join([
        packet.primary_next_step,
        packet.why_now,
        packet.diagnostic_hypothesis.summary,
        packet.recommended_action.objective,
        packet.recommended_action.message_strategy,
        packet.prepared_artifacts[0].body_or_outline,
    ]).lower()

    assert packet.job_type == "customer_outreach"
    assert packet.recommended_action.action_type == "initiate_customer_call"
    assert packet.contact_plan.channel == "working_session_request"
    assert packet.bucket_trace.inputs["blocked_value_path"] is True
    assert "legacy dispatch integration" in rendered
    assert "route optimization" in rendered
    assert "owner" in rendered
    assert "recovery date" in rendered or "date" in rendered
    assert "generic adoption nudges" in rendered
    assert "try the feature" not in rendered
    assert "invite more users" not in rendered
    assert packet.diagnostic_hypothesis.unknowns == ()
    assert any(
        step.supports == "blocked_value_path_recovery"
        for step in packet.evidence_chain
    )


def test_incomplete_source_coverage_blocks_customer_facing_recovery():
    inputs = _pinehill_like_packet_inputs(
        adoption=None,
        entitlements=(),
        usage_signals=(),
    )

    packet = build_work_packet(inputs)

    assert packet.job_type == "needs_data"
    assert packet.recommended_action.action_type == "recommend_next_best_action"
    assert "adoption_summary" in packet.diagnostic_hypothesis.unknowns
    assert "entitlements" in packet.diagnostic_hypothesis.unknowns
    assert "product_usage" in packet.diagnostic_hypothesis.unknowns
    assert planned_customer_draft(inputs) is None
    assert "Do not draft customer-facing language" in packet.recommended_action.message_strategy


def test_sweep_trips_governed_recovery_action_on_fixture_book(runtime_conn):
    runtime_conn.execute("BEGIN")
    try:
        orch, _authority = setup_roster(runtime_conn, tenant=T1)
        gate = ActionGate(
            runtime_conn,
            tenant_id=T1,
            actor_principal_id=orch,
            verdict_source=FixtureVerdictSource(),
            now=CLOCK,
        )

        sweep = run_time_to_value_sweep(
            build_sweep_fixture_data_plane(tenant_id=DEFAULT_TENANT),
            DEFAULT_TENANT,
            gate,
            sweep_principal_id=orch,
            as_of="2026-06-27",
        )
    finally:
        runtime_conn.rollback()

    acme = next(item for item in sweep.work_items if item.account_id == ACME_LOGISTICS)
    assert acme.recommended_action == "draft_customer_outreach"
    assert acme.proposal is not None
    assert acme.proposal.action_type == "draft_customer_outreach"
    assert acme.work_packet is not None
    assert acme.work_packet.recommended_action.action_type == "initiate_customer_call"
    assert acme.work_packet.bucket_trace.matched[0] == "blocked_value_path_recovery"


def _pinehill_like_packet_inputs(
    *,
    adoption: AdoptionSummary | None | object = SimpleNamespace(),
    entitlements: tuple[Entitlement, ...] | object = SimpleNamespace(),
    usage_signals: tuple[UsageSignal, ...] | object = SimpleNamespace(),
) -> PacketInputs:
    account = CRMAccount(
        account_id="acct-pinehill",
        name="Pinehill Transport",
        owner_id="csm-102",
        industry="transportation",
    )
    contact = CRMContact(
        contact_id="contact-dennis",
        account_id=account.account_id,
        email="dennis@pinehill.example",
        name="Dennis Gruber",
        role="fleet_manager",
        title="Fleet Manager",
        consent_to_contact=True,
    )
    case = CRMCase(
        case_id="case-legacy-dispatch",
        account_id=account.account_id,
        status="Open",
        priority="High",
        origin="Email",
        subject="Integration with legacy dispatch system failing",
        created_at="2026-06-10T00:00:00Z",
    )
    resolved_adoption = (
        AdoptionSummary(
            account_id=account.account_id,
            active_users=6,
            licensed_users=25,
            active_assets=9,
            entitled_assets=50,
            adoption_rate=0.18,
            underused_capabilities=("route_optimization",),
            measured_at="2026-07-28T00:00:00Z",
        )
        if isinstance(adoption, SimpleNamespace)
        else adoption
    )
    resolved_entitlements = (
        (
            Entitlement(account.account_id, "core_telematics", 50, "assets", "2026-03-10"),
            Entitlement(account.account_id, "route_optimization", 50, "assets", "2026-03-10"),
        )
        if isinstance(entitlements, SimpleNamespace)
        else entitlements
    )
    resolved_usage_signals = (
        (
            UsageSignal(
                "signal-sync-failures",
                account.account_id,
                "company",
                None,
                "centralize_integration_sync_failures",
                1.0,
                "count",
                "2026-07-28T00:00:00Z",
                "centralize_posthog:derived_fixture",
            ),
        )
        if isinstance(usage_signals, SimpleNamespace)
        else usage_signals
    )
    return PacketInputs(
        tenant_id="ultra-demo",
        account=account,
        as_of=AS_OF,
        disposition="propose_customer_action",
        action="initiate_customer_call",
        motion="working_session",
        priority_score=62,
        priority_factors=(
            SimpleNamespace(name="success_plan_overdue"),
            SimpleNamespace(name="low_seat_penetration"),
            SimpleNamespace(name="feature_depth_gap"),
            SimpleNamespace(name="health_yellow"),
        ),
        evidence=(),
        contacts=(contact,),
        selected_contact=contact,
        recipient_role="champion",
        recipient_resolution="backend_recipient_resolver",
        customer_contact_allowed=True,
        proposal_id="proposal-pinehill",
        proposal_status="pending",
        draft_body=None,
        cases=(case,),
        success_plans=(
            SuccessPlan(
                "plan-pinehill",
                account.account_id,
                "active",
                ("legacy_dispatch_bridge", "route_optimization_activation"),
                "2026-06-17",
            ),
        ),
        usage_signals=resolved_usage_signals,
        milestones=(
            TimeToValueMilestone(
                account.account_id,
                "configure_routing",
                "2026-06-17",
                "2026-07-26T00:00:00Z",
                ("signal-sync-failures",),
            ),
        ),
        opportunities=(),
        internal_bridge_decision=None,
        content_route_title=None,
        book_size=1,
        accounts_scanned=1,
        company=CSCompany(
            account.account_id,
            account.name,
            "transportation",
            8500000,
            "onboarding",
            "Active",
            "2026-03-10",
            "2027-03-10",
            "csm-102",
            47.5,
        ),
        health=HealthScore(
            account.account_id,
            47.5,
            "yellow",
            ("activation_stalled", "usage_decline"),
            "2026-07-28T00:00:00Z",
        ),
        adoption=resolved_adoption,
        entitlements=resolved_entitlements,
        stakeholders=(
            StakeholderRelationship(
                account.account_id,
                contact.contact_id,
                "champion",
                "strong",
                "2026-07-18T00:00:00Z",
                1,
            ),
            StakeholderRelationship(
                account.account_id,
                "contact-amy",
                "technical_lead",
                "moderate",
                "2026-07-15T00:00:00Z",
                2,
            ),
        ),
        ctas=(
            CTA(
                "cta-pinehill",
                account.account_id,
                "Activation milestone at risk",
                "High",
                "open",
                "2026-07-30",
                "csm-102",
            ),
        ),
        communication_signals=(
            CommunicationSignal(
                "comms-pinehill-email",
                account.account_id,
                contact.contact_id,
                "email",
                "inbound",
                "2026-07-18T00:00:00Z",
                10.0,
            ),
        ),
        internal_notes=(
            InternalCommsNote(
                "note-pinehill",
                account.account_id,
                "csm-102",
                "2026-07-18T00:00:00Z",
                "Dennis is still engaged; route help content should target legacy dispatch workflow.",
                "csm_note",
            ),
        ),
        onboarding_projects=(
            OnboardingProject(
                "project-pinehill",
                account.account_id,
                "Pinehill Transport Onboarding",
                2,
                "Running late",
                "csm-102",
                "running_late",
                "2026-03-10",
                "2026-03-10",
                "2026-07-01",
                None,
                8500000,
            ),
        ),
        onboarding_phases=(
            OnboardingPhase(
                "phase-pinehill-integration",
                "project-pinehill",
                "Legacy dispatch integration",
                "2026-05-01",
                "2026-05-01",
                "2026-06-17",
                None,
                "At risk",
                False,
            ),
        ),
        onboarding_tasks=(
            OnboardingTask(
                "task-pinehill-connector",
                "project-pinehill",
                "phase-pinehill-integration",
                "Configure legacy dispatch connector",
                "In progress",
                "2026-05-01",
                "2026-06-17",
                None,
                True,
                ("amy-zhao",),
            ),
        ),
    )
