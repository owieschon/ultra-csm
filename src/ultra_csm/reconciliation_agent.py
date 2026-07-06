"""Reconciliation agent (Harvest 31 / report 52).

Reconciles what CS tools report (health score, CRM/CTA/case state) against
what the customer is actually experiencing in the product (telemetry/usage
signals), for one account. Tier 1 (this module's ``gather_signals``) is
pure, deterministic gathering of already-computed divergence/lens factors
-- no LLM, no gate, no proposal creation. Phase 2 adds a guarded LLM slot
producing a plain-English explanation and (a deliberate, owner-ratified
deviation from ADR-005) judge-gated candidate divergences -- see this
module's ``explain`` function once added.

Tier 1 deliberately does NOT call ``run_risk_lens``/``run_expansion_lens``:
their private ``_item_for_account`` helpers unconditionally call
``gate.propose(...)``, a real governance-DB write, on every fired factor
set -- wrong for a read-only reconciliation lookup (see PROGRESS.md's
LEDGER #1). This module instead calls the same lenses' PURE factor
functions directly (``_risk_factors``/``_expansion_factors``), the exact
computation ``_item_for_account`` uses before it creates a proposal.
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.agent1.lens_expansion import ExpansionLensWeights, _expansion_factors
from ultra_csm.agent1.lens_risk import RiskLensWeights, _risk_factors
from ultra_csm.agent1.sweep import _person_layer_inputs, _trajectory_decline_evaluation
from ultra_csm.data_plane import CustomerDataPlane, EvidenceRef
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.value_model import ValueFactor, build_customer_value_model

_LENS_ORDER = ("value_model", "risk_lens", "expansion_lens")


@dataclass(frozen=True)
class DeterministicSignal:
    """One Tier-1 (deterministic) reconciliation signal -- an already-
    computed ``ValueFactor``, deduplicated across whichever lens(es)
    surfaced it. ``origin`` is always ``"deterministic"``; there is no
    ``disclaimer`` field here by design (Decisions: a disclaimer belongs
    only to non-deterministic, LLM-generated output -- adding one here
    would blur the exact distinction this dispatch exists to make)."""

    origin: str
    name: str
    value: float
    contribution: int
    evidence: tuple[EvidenceRef, ...]
    surfaced_by_lenses: tuple[str, ...]


def gather_signals(
    data_plane: CustomerDataPlane,
    account_id: str,
    *,
    as_of: str,
    snapshot_store: SnapshotStore | None = None,
) -> tuple[DeterministicSignal, ...] | None:
    """Gather every deterministic divergence/lens factor for *account_id*,
    deduplicated. Returns ``None`` when the account or its required CS
    data is missing (mirrors ``_item_for_account``'s own fail-closed
    contract). Pure -- no gate, no proposal, no LLM call."""

    account = data_plane.crm.get_account(account_id)
    if account is None:
        return None
    company = data_plane.cs.get_company(account_id)
    health = data_plane.cs.get_health_score(account_id)
    adoption = data_plane.cs.get_adoption_summary(account_id)
    if company is None or health is None or adoption is None:
        return None

    entitlements = tuple(data_plane.telemetry.list_entitlements(account_id))
    usage_signals = tuple(data_plane.telemetry.list_usage_signals(account_id))
    plans = tuple(data_plane.cs.list_success_plans(account_id))
    ctas = tuple(data_plane.cs.list_ctas(account_id, status="open"))
    cases = tuple(data_plane.crm.list_cases(account_id))
    opportunities = tuple(data_plane.crm.list_opportunities(account_id))
    stakeholders, job_changes = _person_layer_inputs(data_plane, account_id)

    model = build_customer_value_model(
        account=account,
        company=company,
        health=health,
        adoption=adoption,
        entitlements=entitlements,
        usage_signals=usage_signals,
        success_plans=plans,
        stakeholders=stakeholders,
        job_changes=job_changes,
        as_of=as_of,
    )

    trajectory = _trajectory_decline_evaluation(
        snapshot_store, account_id=account_id, model=model,
    )
    risk_factors = _risk_factors(
        model,
        account=account,
        arr_cents=company.arr_cents,
        arr_observed_at=company.original_contract_date,
        health_band=health.band,
        health_observed_at=health.measured_at,
        ctas=ctas,
        plans=plans,
        cases=cases,
        as_of=as_of,
        trajectory_factor=trajectory.factor,
        weights=RiskLensWeights(),
    )
    expansion_factors = _expansion_factors(
        model,
        account=account,
        arr_cents=company.arr_cents,
        arr_observed_at=company.original_contract_date,
        adoption_measured_at=adoption.measured_at,
        opportunities=opportunities,
        snapshot_store=snapshot_store,
        weights=ExpansionLensWeights(),
    )

    return _dedupe_signals(
        (
            ("value_model", model.divergences),
            ("risk_lens", risk_factors),
            ("expansion_lens", expansion_factors),
        ),
    )


def _dedupe_signals(
    groups: tuple[tuple[str, tuple[ValueFactor, ...]], ...],
) -> tuple[DeterministicSignal, ...]:
    """Collapse the same fact (same ``name`` + ``evidence``) surfaced by
    more than one lens into one signal, recording every lens that
    surfaced it. The FIRST group a fact appears in is canonical (groups
    are passed in ``_LENS_ORDER``, so ``value_model``'s unweighted
    ``contribution`` wins over a lens's ``_scale_factor``-reweighted
    copy of the same fact -- see PROGRESS.md LEDGER #2)."""

    order: list[tuple] = []
    by_key: dict[tuple, dict] = {}
    for lens_name, factors in groups:
        for factor in factors:
            evidence_key = tuple(
                (ref.source, ref.source_id, ref.field, ref.observed_at)
                for ref in factor.evidence
            )
            key = (factor.name, evidence_key)
            if key not in by_key:
                by_key[key] = {"factor": factor, "surfaced_by": []}
                order.append(key)
            by_key[key]["surfaced_by"].append(lens_name)

    return tuple(
        DeterministicSignal(
            origin="deterministic",
            name=by_key[key]["factor"].name,
            value=by_key[key]["factor"].value,
            contribution=by_key[key]["factor"].contribution,
            evidence=by_key[key]["factor"].evidence,
            surfaced_by_lenses=tuple(by_key[key]["surfaced_by"]),
        )
        for key in order
    )
