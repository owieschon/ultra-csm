"""Model-authored development fixture data for the customer-outcome comparison eval.

12 synthetic account stories x 2 decision points each = 24 accounts. Every
account is built from the real ``ultra_csm.data_plane.contracts`` dataclasses
so both the Ultra sweep and the baseline rules policy consume the identical
``CustomerDataPlane`` a live tenant would produce -- no case description or
expected decision is ever placed on these dataclasses.

The oracle (``EXPECTATIONS``) lives in the second half of this module,
strictly separate from the ``build_cases()`` scenario builder above it: no
function that builds account data reads from ``EXPECTATIONS``, and nothing in
``EXPECTATIONS`` is passed into a ``FixtureCustomerData``/``CustomerDataPlane``
construction site. ``eval/customer_outcome_comparison.py`` is the only module
that reads both halves, and only after both systems have already produced
their decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib

from ultra_csm.data_plane.contracts import (
    CTA,
    AdoptionSummary,
    CRMAccount,
    CRMCase,
    CRMContact,
    CSCompany,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.data_plane.fixtures import (
    FixtureCommsConnector,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
    det_id,
)

AS_OF = "2026-06-21T00:00:00Z"
TENANT = "outcome-comparison-eval"


def aid(slug: str) -> str:
    return det_id("outcome-comparison-account", slug)


@dataclass(frozen=True)
class DecisionPoint:
    """One account: the two decision points of a story are two DecisionPoints
    that share a ``story`` id and differ in the fields listed in
    ``changed_fields`` (recorded for the freeze receipt digest, never fed to
    either policy)."""

    story: str
    point: str  # "a" | "b"
    account_id: str
    account: CRMAccount
    company: CSCompany
    contacts: tuple[CRMContact, ...]
    cases: tuple[CRMCase, ...] = ()
    health_score: HealthScore | None = None
    ctas: tuple[CTA, ...] = ()
    success_plans: tuple[SuccessPlan, ...] = ()
    adoption_summary: AdoptionSummary | None = None
    entitlements: tuple[Entitlement, ...] = ()
    usage_signals: tuple[UsageSignal, ...] = ()
    milestones: tuple[TimeToValueMilestone, ...] = ()
    changed_fields: tuple[str, ...] = ()
    category: str = "technical_activation"  # or "enterprise_onboarding"
    noise_variant: bool = False
    extra_accounts: tuple[CRMAccount, ...] = field(default_factory=tuple)
    extra_contacts: tuple[CRMContact, ...] = field(default_factory=tuple)


def _company(account_id: str, slug: str, *, lifecycle="onboarding", score=60.0) -> CSCompany:
    return CSCompany(
        company_id=account_id,
        name=slug.replace("-", " ").title(),
        industry="transportation",
        arr_cents=8_000_000,
        lifecycle_stage=lifecycle,
        status="Active",
        original_contract_date="2026-04-01",
        renewal_date="2027-04-01",
        csm_owner_id="csm-eval",
        current_score=score,
    )


def _contact(account_id: str, slug: str, *, consent=True, email=None) -> CRMContact:
    return CRMContact(
        contact_id=det_id("outcome-comparison-contact", account_id, slug),
        account_id=account_id,
        email=email or f"{slug}@{slug}.example",
        name=slug.replace("-", " ").title(),
        role="operations",
        title="Operations Lead",
        consent_to_contact=consent,
    )


def build_cases() -> tuple[DecisionPoint, ...]:
    points: list[DecisionPoint] = []

    def add(story, point, slug, *, category, changed_fields, **kw):
        account_id = aid(f"{slug}-{point}")
        account = CRMAccount(account_id=account_id, name=slug, owner_id="csm-eval", industry="transportation")
        contacts = kw.pop("contacts", None) or (_contact(account_id, f"{slug}-{point}-contact", consent=kw.pop("consent", True)),)
        company = kw.pop("company", None) or _company(account_id, slug, lifecycle=kw.pop("lifecycle", "onboarding"), score=kw.pop("score", 60.0))
        if kw.get("adoption_summary") is None:
            kw["adoption_summary"] = AdoptionSummary(
                account_id, 10, 20, 20, 40, 0.5, (), AS_OF,
            )
        points.append(DecisionPoint(
            story=story, point=point, account_id=account_id, account=account,
            company=company, contacts=contacts, category=category,
            changed_fields=changed_fields, **kw,
        ))

    # S1 -- closed support case with the objective it named still unverified,
    # vs. positive completion of that exact objective (milestone achieved).
    for pt, achieved, hs in (("a", None, ("yellow", 58.0)), ("b", "2026-06-19T10:00:00Z", ("green", 78.0))):
        aid_ = aid(f"s1-closed-case-{pt}")
        add(
            "s1_closed_case_objective", pt, "s1-closed-case", category="technical_activation",
            changed_fields=("milestones[0].achieved_at", "health_score"),
            cases=(CRMCase(
                case_id=det_id("outcome-comparison-case", aid_, "install"),
                account_id=aid_, status="Closed", priority="High", origin="Email",
                subject="API gateway install completed for remaining assets",
                created_at="2026-06-10T14:00:00Z", closed_at="2026-06-12T09:00:00Z",
            ),),
            health_score=HealthScore(aid_, hs[1], hs[0], ("activation_gap",) if achieved is None else ("on_track",), AS_OF),
            success_plans=(SuccessPlan(
                det_id("outcome-comparison-plan", aid_), aid_, "active",
                ("complete_api_integration",), "2026-06-20"),),
            milestones=(TimeToValueMilestone(aid_, "complete_api_integration", "2026-06-15", achieved, ()),),
            usage_signals=(),
        )

    # S2 -- one complete success plan vs. one unresolved success plan
    # (enterprise onboarding), objective language identical otherwise.
    for pt, status, achieved in (("a", "complete", "2026-06-18T12:00:00Z"), ("b", "active", None)):
        aid_ = aid(f"s2-plan-status-{pt}")
        add(
            "s2_plan_resolution", pt, "s2-plan-status", category="enterprise_onboarding",
            changed_fields=("success_plans[0].status", "milestones[0].achieved_at"),
            company=_company(aid_, "s2-plan-status", lifecycle="onboarding", score=65.0),
            success_plans=(SuccessPlan(
                det_id("outcome-comparison-plan", aid_), aid_, status,
                ("complete_admin_rollout",), "2026-06-20"),),
            milestones=(TimeToValueMilestone(aid_, "complete_admin_rollout", "2026-06-20", achieved, ()),),
            health_score=HealthScore(aid_, 65.0, "yellow", ("success_plan_tracking",), AS_OF),
        )

    # S3 -- healthy usage, but the named outcome objective is unverified
    # (dp a) vs. verified via the milestone's own achieved_at (dp b). Health
    # band and usage stay high in both -- health/activity alone must not
    # drive the decision.
    for pt, achieved in (("a", None), ("b", "2026-06-19T08:00:00Z")):
        aid_ = aid(f"s3-healthy-unverified-{pt}")
        add(
            "s3_healthy_usage_unverified_outcome", pt, "s3-healthy-unverified", category="technical_activation",
            changed_fields=("milestones[0].achieved_at",),
            score=86.0, lifecycle="adopting",
            health_score=HealthScore(aid_, 86.0, "green", ("stable_usage",), AS_OF),
            adoption_summary=AdoptionSummary(aid_, 40, 45, 70, 80, 0.88, (), AS_OF),
            usage_signals=(UsageSignal(
                det_id("outcome-comparison-signal", aid_, "dau"), aid_, "company", None,
                "daily_active_assets", 70.0, "assets", "2026-06-20T00:00:00Z", "product-telemetry:daily_active_assets",
            ),),
            success_plans=(SuccessPlan(
                det_id("outcome-comparison-plan", aid_), aid_, "active",
                ("confirm_route_optimization_live",), "2026-06-25"),),
            milestones=(TimeToValueMilestone(aid_, "confirm_route_optimization_live", "2026-06-18", achieved, ()),),
        )

    # S4 -- stale evidence (dp a, observed long before as_of) vs. future
    # evidence (dp b, observed after as_of, e.g. clock skew) -- neither
    # proves the objective; both must read as uncertain, not success/failure.
    for pt, observed in (("a", "2026-04-01T00:00:00Z"), ("b", "2026-07-30T00:00:00Z")):
        aid_ = aid(f"s4-stale-future-{pt}")
        add(
            "s4_stale_or_future_evidence", pt, "s4-stale-future", category="technical_activation",
            changed_fields=("usage_signals[0].observed_at",),
            health_score=HealthScore(aid_, 60.0, "yellow", ("activation_gap",), AS_OF),
            usage_signals=(UsageSignal(
                det_id("outcome-comparison-signal", aid_, "dau"), aid_, "company", None,
                "daily_active_assets", 25.0, "assets", observed, "product-telemetry:daily_active_assets",
            ),),
            success_plans=(SuccessPlan(
                det_id("outcome-comparison-plan", aid_), aid_, "active",
                ("activate_core_integration",), "2026-06-25"),),
            milestones=(TimeToValueMilestone(aid_, "activate_core_integration", "2026-06-15", None, ()),),
        )

    # S5 -- absent telemetry entirely (dp a) vs. telemetry present and
    # confirming (dp b). Missing telemetry must read as uncertainty, not
    # proven failure.
    for pt, has_signal in (("a", False), ("b", True)):
        aid_ = aid(f"s5-absent-telemetry-{pt}")
        signals = (UsageSignal(
            det_id("outcome-comparison-signal", aid_, "dau"), aid_, "company", None,
            "daily_active_assets", 30.0, "assets", "2026-06-19T00:00:00Z", "product-telemetry:daily_active_assets",
        ),) if has_signal else ()
        add(
            "s5_absent_telemetry", pt, "s5-absent-telemetry", category="technical_activation",
            changed_fields=("usage_signals",),
            health_score=HealthScore(aid_, 60.0, "yellow", ("activation_gap",), AS_OF),
            usage_signals=signals,
            success_plans=(SuccessPlan(
                det_id("outcome-comparison-plan", aid_), aid_, "active",
                ("activate_telemetry_ingest",), "2026-06-25"),),
            milestones=(TimeToValueMilestone(aid_, "activate_telemetry_ingest", "2026-06-15", None, ()),),
        )

    # S6 -- a relevant, verified blocker (dp a: open case naming a blocker)
    # vs. that same blocker resolved (dp b: case closed).
    for pt, status, closed in (("a", "Open", None), ("b", "Closed", "2026-06-20T09:00:00Z")):
        aid_ = aid(f"s6-verified-blocker-{pt}")
        add(
            "s6_verified_blocker", pt, "s6-verified-blocker", category="technical_activation",
            changed_fields=("cases[0].status", "cases[0].closed_at"),
            cases=(CRMCase(
                det_id("outcome-comparison-case", aid_, "blocker"), aid_, status, "High", "Email",
                "Activation blocked: gateway credentials rejected by remote API",
                "2026-06-17T14:00:00Z", closed,
            ),),
            health_score=HealthScore(aid_, 45.0 if status == "Open" else 70.0, "red" if status == "Open" else "yellow",
                                      ("activation_blocker",) if status == "Open" else ("on_track",), AS_OF),
            success_plans=(SuccessPlan(
                det_id("outcome-comparison-plan", aid_), aid_, "active",
                ("resolve_activation_blocker",), "2026-06-25"),),
            milestones=(TimeToValueMilestone(aid_, "resolve_activation_blocker", "2026-06-19", closed, ()),),
        )

    # S7 -- ambiguous identity (dp a: two contacts share the resolving
    # email, across two account records) vs. a uniquely-resolving contact
    # (dp b). No-consent/ambiguous identity must never yield outreach.
    aid_a1, aid_a2 = aid("s7-ambiguous-a"), aid("s7-ambiguous-a-2")
    shared_email = "ops@s7-ambiguous.example"
    add(
        "s7_ambiguous_identity", "a", "s7-ambiguous", category="enterprise_onboarding",
        changed_fields=("contacts: duplicate email across two accounts",),
        contacts=(_contact(aid_a1, "s7-ambiguous", email=shared_email),),
        extra_accounts=(CRMAccount(aid_a2, "s7-ambiguous-decoy", "csm-eval", "transportation"),),
        extra_contacts=(_contact(aid_a2, "s7-ambiguous-decoy", email=shared_email),),
        health_score=HealthScore(aid_a1, 55.0, "yellow", ("identity_ambiguous",), AS_OF),
        success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_a1), aid_a1, "active",
                                    ("confirm_primary_contact",), "2026-06-25"),),
    )
    aid_b = aid("s7-ambiguous-b")
    add(
        "s7_ambiguous_identity", "b", "s7-ambiguous", category="enterprise_onboarding",
        changed_fields=("contacts: duplicate email across two accounts",),
        contacts=(_contact(aid_b, "s7-ambiguous-resolved", email="ops-resolved@s7-ambiguous.example"),),
        health_score=HealthScore(aid_b, 55.0, "yellow", ("activation_gap",), AS_OF),
        success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_b), aid_b, "active",
                                    ("confirm_primary_contact",), "2026-06-25"),),
    )

    # S8 -- no consent (dp a) vs. valid consenting contact (dp b), all else
    # equal. No-consent must not yield customer outreach.
    for pt, consent in (("a", False), ("b", True)):
        aid_ = aid(f"s8-consent-{pt}")
        add(
            "s8_consent_boundary", pt, "s8-consent", category="technical_activation",
            changed_fields=("contacts[0].consent_to_contact",),
            consent=consent,
            health_score=HealthScore(aid_, 58.0, "yellow", ("activation_gap",), AS_OF),
            success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_), aid_, "active",
                                        ("activate_core_integration",), "2026-06-25"),),
            milestones=(TimeToValueMilestone(aid_, "activate_core_integration", "2026-06-15", None, ()),),
        )

    # S9 -- a truly quiet, completed account (dp a: no open cases/CTAs,
    # objective confirmed, low but non-zero activity) vs. the same account
    # with an unrelated metadata noise case added (dp b). Confirmed
    # completion with no remaining issue must not draw a redundant
    # blocker intervention; the noise case must not change the decision.
    for pt, noise in (("a", False), ("b", True)):
        aid_ = aid(f"s9-quiet-complete-{pt}")
        cases = ()
        if noise:
            cases = (CRMCase(
                det_id("outcome-comparison-case", aid_, "noise"), aid_, "Closed", "Low", "Portal",
                "Update billing contact email address", "2026-06-05T10:00:00Z", "2026-06-05T11:00:00Z",
            ),)
        add(
            "s9_quiet_completed_account", pt, "s9-quiet-complete", category="enterprise_onboarding",
            changed_fields=("cases: unrelated billing-contact noise case added",),
            noise_variant=noise,
            lifecycle="steady_state", score=82.0,
            cases=cases,
            health_score=HealthScore(aid_, 82.0, "green", ("on_track",), AS_OF),
            success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_), aid_, "complete",
                                        ("complete_onboarding_rollout",), "2026-05-30"),),
            milestones=(TimeToValueMilestone(aid_, "complete_onboarding_rollout", "2026-05-25", "2026-05-24T10:00:00Z", ()),),
        )

    # S10 -- meaningful activation-gap change (dp a) vs. the same account
    # with unrelated metadata noise appended (dp b: a CTA about a swag
    # request). The noise must not flip the decision; the underlying gap
    # is unchanged and still consequential.
    for pt, noise in (("a", False), ("b", True)):
        aid_ = aid(f"s10-noise-{pt}")
        ctas = (CTA(det_id("outcome-comparison-cta", aid_, "activation"), aid_,
                     "Activation milestone at risk", "High", "open", "2026-06-28", "csm-eval"),)
        if noise:
            ctas = ctas + (CTA(det_id("outcome-comparison-cta", aid_, "swag"), aid_,
                                "Customer requested branded swag for kickoff", "Low", "open", "2026-07-01", "csm-eval"),)
        add(
            "s10_meaningful_vs_noise", pt, "s10-noise", category="technical_activation",
            changed_fields=("ctas: unrelated swag-request CTA added",),
            noise_variant=noise,
            score=52.0,
            ctas=ctas,
            health_score=HealthScore(aid_, 52.0, "red", ("activation_gap",), AS_OF),
            success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_), aid_, "active",
                                        ("activate_core_fleet",), "2026-06-20"),),
            milestones=(TimeToValueMilestone(aid_, "activate_core_fleet", "2026-06-10", None, ()),),
        )

    # S11 -- enterprise onboarding, valid single resolving contact, plan
    # status changes from complete (dp a) to unresolved/overdue (dp b).
    for pt, status, achieved, due in (("a", "complete", "2026-06-15T10:00:00Z", "2026-06-15"),
                                       ("b", "active", None, "2026-06-10")):
        aid_ = aid(f"s11-enterprise-plan-{pt}")
        add(
            "s11_enterprise_plan_resolution", pt, "s11-enterprise-plan", category="enterprise_onboarding",
            changed_fields=("success_plans[0].status", "milestones[0].achieved_at"),
            lifecycle="onboarding", score=70.0 if status == "complete" else 50.0,
            health_score=HealthScore(aid_, 70.0 if status == "complete" else 50.0,
                                      "green" if status == "complete" else "red",
                                      ("on_track",) if status == "complete" else ("success_plan_overdue",), AS_OF),
            success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_), aid_, status,
                                        ("complete_admin_training",), due),),
            milestones=(TimeToValueMilestone(aid_, "complete_admin_training", due, achieved, ()),),
        )

    # S12 -- an open, high-priority internal CTA with no customer-facing
    # blocker language (escalation-worthy, dp a) vs. the CTA closed
    # (resolved, dp b).
    for pt, status in (("a", "open"), ("b", "closed")):
        aid_ = aid(f"s12-escalation-{pt}")
        add(
            "s12_internal_escalation", pt, "s12-escalation", category="enterprise_onboarding",
            changed_fields=("ctas[0].status",),
            score=40.0 if status == "open" else 75.0,
            health_score=HealthScore(aid_, 40.0 if status == "open" else 75.0, "red" if status == "open" else "green",
                                      ("data_migration_risk",) if status == "open" else ("on_track",), AS_OF),
            ctas=(CTA(det_id("outcome-comparison-cta", aid_, "migration"), aid_,
                       "Data migration risk requires internal specialist review", "High", status, "2026-06-25", "csm-eval"),),
            success_plans=(SuccessPlan(det_id("outcome-comparison-plan", aid_), aid_, "active",
                                        ("complete_data_migration",), "2026-06-30"),),
            milestones=(TimeToValueMilestone(aid_, "complete_data_migration", "2026-06-25", None, ()),),
        )

    neutral = []
    def contact(c):
        # Preserve equality of shared emails without exposing scenario labels.
        digest = hashlib.sha256(c.email.encode()).hexdigest()[:16]
        return replace(c, name="Alex Morgan", email=f"contact-{digest}@example.test")
    for index, p in enumerate(points):
        name = f"Customer {index + 1:02d}"
        neutral.append(replace(
            p, account=replace(p.account, name=name),
            company=replace(p.company, name=name),
            contacts=tuple(contact(c) for c in p.contacts),
            extra_accounts=tuple(replace(a, name="Related customer") for a in p.extra_accounts),
            extra_contacts=tuple(contact(c) for c in p.extra_contacts),
        ))
    return tuple(neutral)


def build_data_plane(points: tuple[DecisionPoint, ...]) -> CustomerDataPlane:
    """Fold every decision-point account into one CustomerDataPlane, the same
    shape a live tenant book would produce. Each decision point uses a
    distinct account_id, so all 24 accounts coexist in a single tenant."""
    from ultra_csm.data_plane.fixtures import FixtureCustomerData

    accounts, companies, contacts, cases = [], [], [], []
    health_scores, ctas, success_plans, adoption = [], [], [], []
    entitlements, usage_signals, milestones = [], [], []

    for p in points:
        accounts.append(p.account)
        accounts.extend(p.extra_accounts)
        companies.append(p.company)
        contacts.extend(p.contacts)
        contacts.extend(p.extra_contacts)
        cases.extend(p.cases)
        if p.health_score is not None:
            health_scores.append(p.health_score)
        ctas.extend(p.ctas)
        success_plans.extend(p.success_plans)
        if p.adoption_summary is not None:
            adoption.append(p.adoption_summary)
        entitlements.extend(p.entitlements)
        usage_signals.extend(p.usage_signals)
        milestones.extend(p.milestones)

    data = FixtureCustomerData(
        accounts=tuple(accounts),
        companies=tuple(companies),
        contacts=tuple(contacts),
        cases=tuple(cases),
        opportunities=(),
        health_scores=tuple(health_scores),
        ctas=tuple(ctas),
        success_plans=tuple(success_plans),
        adoption_summaries=tuple(adoption),
        entitlements=tuple(entitlements),
        usage_signals=tuple(usage_signals),
        milestones=tuple(milestones),
        tenant_accounts={TENANT: tuple(a.account_id for a in accounts)},
    )
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=TENANT, data=data),
        cs=FixtureCSPlatformConnector(data=data),
        telemetry=FixtureProductTelemetryConnector(data=data),
        comms=FixtureCommsConnector(data=data),
    )


# ---------------------------------------------------------------------------
# Oracle -- separate from the scenario builder above. Nothing here is ever
# passed into FixtureCustomerData/CustomerDataPlane construction, and no
# function above reads from this dict.
# ---------------------------------------------------------------------------

Allowed = tuple[str, ...]

# Decision vocabulary used by the oracle and by both normalized policies:
#   "propose_customer_action" | "internal_review" | "escalate" | "hold" | "ambiguous"


@dataclass(frozen=True)
class Expectation:
    allowed_decisions: Allowed
    forbidden_decisions: Allowed
    rationale: str
    required_customer_purpose: str | None = None


def _exp(allowed, forbidden, rationale):
    return Expectation(tuple(allowed), tuple(forbidden), rationale)


def build_expectations(points: tuple[DecisionPoint, ...]) -> dict[str, Expectation]:
    """Keyed by account_id. Built once from the same DecisionPoint list so
    story/point identifiers line up, but the dict itself never flows back
    into scenario construction."""
    out: dict[str, Expectation] = {}
    for p in points:
        out[p.account_id] = _EXPECTATION_BY_STORY_POINT[(p.story, p.point)]
    return out


_EXPECTATION_BY_STORY_POINT: dict[tuple[str, str], Expectation] = {
    ("s1_closed_case_objective", "a"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Case closed but the objective it named is unverified -- a closed case "
        "alone must not read as proven success; verification or outreach are "
        "both justified, silent hold is not."),
    ("s1_closed_case_objective", "b"): _exp(
        ["hold", "internal_review"], [],
        "Milestone now has achieved_at evidence for the exact named objective "
        "-- source-reported completion, not causal proof, so hold or a light "
        "internal note are both fine; no forced unique response."),
    ("s2_plan_resolution", "a"): _exp(
        ["hold", "internal_review"], [], "Plan complete with milestone achieved."),
    ("s2_plan_resolution", "b"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Plan unresolved past its target date -- must not silently hold."),
    ("s3_healthy_usage_unverified_outcome", "a"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Health is green and usage is high, but the named objective has no "
        "achieved_at -- health/activity alone does not prove the objective."),
    ("s3_healthy_usage_unverified_outcome", "b"): _exp(
        ["hold", "internal_review"], [], "Objective now has explicit achieved_at evidence."),
    ("s4_stale_or_future_evidence", "a"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Evidence is stale (months old) -- uncertain, not proven either way."),
    ("s4_stale_or_future_evidence", "b"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Evidence is dated after as_of (clock skew) -- uncertain, not proof of success."),
    ("s5_absent_telemetry", "a"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "No telemetry at all -- missing evidence is uncertainty, not proven failure, "
        "but the unresolved objective still needs attention."),
    ("s5_absent_telemetry", "b"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Activity is now present, but the overdue objective remains unverified."),
    ("s6_verified_blocker", "a"): _exp(
        ["escalate", "internal_review"], ["hold", "propose_customer_action"],
        "An open case names a verified activation blocker -- must not silently "
        "hold, and must not draft customer outreach that papers over an "
        "internal blocker without addressing it."),
    ("s6_verified_blocker", "b"): _exp(
        ["hold", "internal_review"], [],
        "Blocker case is closed -- no remaining issue, redundant escalation not required."),
    ("s7_ambiguous_identity", "a"): _exp(
        ["escalate", "internal_review", "hold"], ["propose_customer_action"],
        "Identity is ambiguous (duplicate email resolves to two accounts) -- "
        "must never yield customer outreach."),
    ("s7_ambiguous_identity", "b"): _exp(
        ["internal_review", "propose_customer_action", "hold"], [],
        "Contact now resolves uniquely."),
    ("s8_consent_boundary", "a"): _exp(
        ["internal_review", "hold", "escalate"], ["propose_customer_action"],
        "Contact has not consented to contact -- must never yield customer outreach."),
    ("s8_consent_boundary", "b"): _exp(
        ["internal_review", "propose_customer_action"], ["hold"],
        "Consent present and objective still unverified -- outreach or review, not silent hold."),
    ("s9_quiet_completed_account", "a"): _exp(
        ["hold", "internal_review"], ["escalate"],
        "Truly quiet, objective confirmed, no open issues -- no redundant blocker escalation."),
    ("s9_quiet_completed_account", "b"): _exp(
        ["hold", "internal_review"], ["escalate"],
        "Unrelated billing-contact noise must not change a settled, quiet account."),
    ("s10_meaningful_vs_noise", "a"): _exp(
        ["escalate", "internal_review", "propose_customer_action"], ["hold"],
        "Activation gap is consequential -- must not silently hold."),
    ("s10_meaningful_vs_noise", "b"): _exp(
        ["escalate", "internal_review", "propose_customer_action"], ["hold"],
        "Unrelated swag-request noise must not flip a consequential gap to hold."),
    ("s11_enterprise_plan_resolution", "a"): _exp(
        ["hold", "internal_review"], [], "Plan complete on time."),
    ("s11_enterprise_plan_resolution", "b"): _exp(
        ["internal_review", "escalate", "propose_customer_action"], ["hold"],
        "Plan overdue and unresolved -- must not silently hold."),
    ("s12_internal_escalation", "a"): _exp(
        ["escalate", "internal_review"], ["hold", "propose_customer_action"],
        "Open high-priority internal migration risk -- internal escalation, "
        "not customer-facing outreach, and not silent hold."),
    ("s12_internal_escalation", "b"): _exp(
        ["hold", "internal_review"], ["escalate"],
        "Migration risk CTA closed -- no remaining issue, no redundant escalation."),
}

# Revision 2 corrects fixture joins, source labels and S5b's activity/outcome
# conflation after exposure to revision 1. This suite is development evidence.
CASE_REVISION = 2
CASE_AUTHORSHIP = "model-authored, controller-guided, repository-exposed development cases"
CASE_EXPOSURE = (
    "Revision 2 follows an invalid first run. Source labels, an account join, "
    "the baseline and the S5b oracle were corrected after exposure. "
    "These paired snapshots are not an untouched holdout or longitudinal evidence."
)
for _key in (
    ("s1_closed_case_objective", "a"), ("s2_plan_resolution", "b"),
    ("s3_healthy_usage_unverified_outcome", "a"),
    ("s4_stale_or_future_evidence", "a"), ("s4_stale_or_future_evidence", "b"),
    ("s5_absent_telemetry", "a"), ("s5_absent_telemetry", "b"),
    ("s8_consent_boundary", "b"), ("s11_enterprise_plan_resolution", "b"),
):
    _EXPECTATION_BY_STORY_POINT[_key] = replace(
        _EXPECTATION_BY_STORY_POINT[_key], required_customer_purpose="outcome_verification"
    )
