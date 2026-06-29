"""Time-to-Value Accelerator built only on the CSM data plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultra_csm._util import iso_date
from ultra_csm.data_plane import (
    AdoptionSummary,
    CRMAccount,
    CRMCase,
    CRMContact,
    CRMOpportunity,
    CSCompany,
    CTA,
    CustomerDataPlane,
    Entitlement,
    HealthScore,
    SuccessPlan,
    TimeToValueMilestone,
    UsageSignal,
)
from ultra_csm.governance import ActionGate, ActionProposal, proposal_fields_for

RecommendationStatus = Literal[
    "recommend_outreach",
    "blocked_missing_account",
    "blocked_missing_success_context",
    "blocked_missing_telemetry",
    "blocked_contact_consent",
    "escalate_identity",
    "no_action",
]


@dataclass(frozen=True)
class TTVEvidenceBundle:
    account: CRMAccount
    contacts: tuple[CRMContact, ...]
    cases: tuple[CRMCase, ...]
    opportunities: tuple[CRMOpportunity, ...]
    company: CSCompany
    health: HealthScore
    ctas: tuple[CTA, ...]
    success_plans: tuple[SuccessPlan, ...]
    adoption: AdoptionSummary
    entitlements: tuple[Entitlement, ...]
    usage_signals: tuple[UsageSignal, ...]
    milestones: tuple[TimeToValueMilestone, ...]
    open_milestone_gaps: tuple[TimeToValueMilestone, ...]
    evidence_signal_ids: tuple[str, ...]


@dataclass(frozen=True)
class TTVRecommendation:
    status: RecommendationStatus
    account_id: str | None
    reason: str
    evidence: TTVEvidenceBundle | None = None
    contact: CRMContact | None = None
    proposal: ActionProposal | None = None

    @property
    def blocked(self) -> bool:
        return self.status.startswith("blocked_") or self.status == "escalate_identity"


class TimeToValueAccelerator:
    """Agent 1 path: data-plane evidence in, gated CSM proposal out."""

    def __init__(self, data_plane: CustomerDataPlane) -> None:
        self._data_plane = data_plane

    def build_evidence(self, account_id: str, *, as_of: str) -> TTVEvidenceBundle | None:
        account = self._data_plane.crm.get_account(account_id)
        company = self._data_plane.cs.get_company(account_id)
        health = self._data_plane.cs.get_health_score(account_id)
        adoption = self._data_plane.cs.get_adoption_summary(account_id)
        if account is None:
            return None
        if company is None or health is None or adoption is None:
            return None

        contacts = tuple(self._data_plane.crm.list_contacts(account_id))
        cases = tuple(self._data_plane.crm.list_cases(account_id))
        opportunities = tuple(self._data_plane.crm.list_opportunities(account_id))
        ctas = tuple(self._data_plane.cs.list_ctas(account_id, status="open"))
        success_plans = tuple(self._data_plane.cs.list_success_plans(account_id))
        entitlements = tuple(self._data_plane.telemetry.list_entitlements(account_id))
        usage_signals = tuple(self._data_plane.telemetry.list_usage_signals(account_id))
        milestones = tuple(self._data_plane.telemetry.list_ttv_milestones(account_id))
        gaps = tuple(
            m for m in milestones
            if m.achieved_at is None and iso_date(m.expected_by) <= iso_date(as_of)
        )
        signal_ids = {s.signal_id for s in usage_signals}
        evidence_signal_ids = tuple(
            sorted({
                signal_id
                for milestone in gaps
                for signal_id in milestone.evidence_signal_ids
                if signal_id in signal_ids
            })
        )

        return TTVEvidenceBundle(
            account=account,
            contacts=contacts,
            cases=cases,
            opportunities=opportunities,
            company=company,
            health=health,
            ctas=ctas,
            success_plans=success_plans,
            adoption=adoption,
            entitlements=entitlements,
            usage_signals=usage_signals,
            milestones=milestones,
            open_milestone_gaps=gaps,
            evidence_signal_ids=evidence_signal_ids,
        )

    def recommend(
        self,
        account_id: str,
        *,
        as_of: str,
        contact_email: str | None = None,
    ) -> TTVRecommendation:
        evidence = self.build_evidence(account_id, as_of=as_of)
        if evidence is None:
            return TTVRecommendation(
                "blocked_missing_account",
                account_id,
                "CRM account or success context was missing.",
            )
        if not evidence.success_plans or not evidence.ctas:
            return TTVRecommendation(
                "blocked_missing_success_context",
                account_id,
                "No open CTA or success plan grounds a Time-to-Value intervention.",
                evidence=evidence,
            )
        if not evidence.open_milestone_gaps or not evidence.evidence_signal_ids:
            return TTVRecommendation(
                "blocked_missing_telemetry",
                account_id,
                "No raw telemetry-backed open Time-to-Value gap was found.",
                evidence=evidence,
            )

        contact = _select_contact(evidence.contacts, contact_email=contact_email)
        if contact is None or not contact.consent_to_contact:
            return TTVRecommendation(
                "blocked_contact_consent",
                account_id,
                "No consented customer contact is available for outbound draft.",
                evidence=evidence,
                contact=contact,
            )

        return TTVRecommendation(
            "recommend_outreach",
            account_id,
            "Open Time-to-Value milestone gap has CRM, CS-platform, and telemetry evidence.",
            evidence=evidence,
            contact=contact,
        )

    def propose_customer_outreach(
        self,
        account_id: str,
        gate: ActionGate,
        *,
        as_of: str,
        contact_email: str | None = None,
    ) -> TTVRecommendation:
        recommendation = self.recommend(
            account_id,
            as_of=as_of,
            contact_email=contact_email,
        )
        if recommendation.status != "recommend_outreach":
            return recommendation

        assert recommendation.evidence is not None
        assert recommendation.contact is not None
        fields = proposal_fields_for("draft_customer_outreach")
        payload = _proposal_payload(recommendation.evidence, recommendation.contact, as_of)
        proposal = gate.propose(
            intent="agent1_time_to_value",
            payload=payload,
            grounding_ref=f"ttv:{account_id}:{as_of}",
            cause_ref=f"agent1:ttv:{account_id}:{as_of}",
            **fields,
        )
        return TTVRecommendation(
            recommendation.status,
            account_id,
            recommendation.reason,
            evidence=recommendation.evidence,
            contact=recommendation.contact,
            proposal=proposal,
        )

    def propose_customer_outreach_for_email(
        self,
        email: str,
        gate: ActionGate,
        *,
        as_of: str,
    ) -> TTVRecommendation:
        resolution = self._data_plane.crm.resolve_account_by_email(email)
        if resolution.state != "exactly_one" or resolution.account_id is None:
            return TTVRecommendation(
                "escalate_identity",
                None,
                f"Identity resolution returned {resolution.state}; no account was auto-picked.",
            )
        return self.propose_customer_outreach(
            resolution.account_id,
            gate,
            as_of=as_of,
            contact_email=email,
        )


def _select_contact(
    contacts: tuple[CRMContact, ...],
    *,
    contact_email: str | None,
) -> CRMContact | None:
    if contact_email is not None:
        return next((c for c in contacts if c.email.lower() == contact_email.lower()), None)
    return next((c for c in contacts if c.consent_to_contact), None)


def _proposal_payload(
    evidence: TTVEvidenceBundle,
    contact: CRMContact,
    as_of: str,
) -> dict:
    return {
        "account_id": evidence.account.account_id,
        "account_name": evidence.account.name,
        "contact_id": contact.contact_id,
        "contact_email": contact.email,
        "as_of": as_of,
        "draft_channel": "email",
        "subject": f"Time-to-Value check-in for {evidence.account.name}",
        "body": _draft_body(evidence, contact),
        "evidence": {
            "crm": {
                "account_id": evidence.account.account_id,
                "contact_id": contact.contact_id,
                "case_ids": [c.case_id for c in evidence.cases],
                "opportunity_ids": [o.opportunity_id for o in evidence.opportunities],
            },
            "cs_platform": {
                "company_id": evidence.company.company_id,
                "health_band": evidence.health.band,
                "cta_ids": [c.cta_id for c in evidence.ctas],
                "success_plan_ids": [p.plan_id for p in evidence.success_plans],
                "adoption_measured_at": evidence.adoption.measured_at,
            },
            "telemetry": {
                "entitlements": [e.capability for e in evidence.entitlements],
                "usage_signal_ids": list(evidence.evidence_signal_ids),
                "open_milestones": [m.milestone for m in evidence.open_milestone_gaps],
            },
        },
    }


def _draft_body(evidence: TTVEvidenceBundle, contact: CRMContact) -> str:
    gaps = ", ".join(m.milestone for m in evidence.open_milestone_gaps)
    cta = evidence.ctas[0].reason if evidence.ctas else "activation follow-up"
    return (
        f"Hi {contact.name}, I noticed {evidence.account.name} has an open "
        f"Time-to-Value milestone gap ({gaps}) and a related CTA: {cta}. "
        "I can help review the adoption signals and unblock the next step."
    )
