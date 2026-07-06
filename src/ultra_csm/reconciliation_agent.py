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

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ultra_csm.agent1.lens_expansion import ExpansionLensWeights, _expansion_factors
from ultra_csm.agent1.lens_risk import RiskLensWeights, _risk_factors
from ultra_csm.agent1.slot_b import (
    LIVE_MAX_RETRIES,
    LIVE_SLOT_B_MODEL_ID,
    LIVE_TIMEOUT_S,
    _extract_json_object,
    _text_from_message,
)
from ultra_csm.agent1.sweep import _person_layer_inputs, _trajectory_decline_evaluation
from ultra_csm.data_plane import CustomerDataPlane, EvidenceRef
from ultra_csm.snapshot_store import SnapshotStore
from ultra_csm.value_model import ValueFactor, build_customer_value_model

if TYPE_CHECKING:
    from ultra_csm.cost_tracker import CostTracker

_LENS_ORDER = ("value_model", "risk_lens", "expansion_lens")

RECONCILIATION_PROMPT_VERSION = "agent1-reconciliation-v1"
RECONCILIATION_PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "prompts"
    / "agent1_reconciliation_v1.md"
)
LIVE_RECONCILIATION_MODEL_ID = LIVE_SLOT_B_MODEL_ID
FIXTURE_RECONCILIATION_MODEL_ID = "fixture-agent1-reconciliation-v1"
MAX_CANDIDATE_DIVERGENCES = 3

# Fixed, non-LLM-authored disclaimer text (Decisions: an LLM must never
# write its own disclaimer). Every non-deterministic field carries its
# own copy of the relevant one below.
EXPLANATION_DISCLAIMER = (
    "Model-generated explanation -- may be incomplete or mischaracterize the "
    "underlying evidence. Verify against the cited sources before acting."
)
CANDIDATE_DISCLAIMER = (
    "Unverified AI hypothesis, not a confirmed finding -- may be wrong. "
    "Judge-scored for grounding but not human-confirmed."
)


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


def _raw_evidence_pool(
    data_plane: CustomerDataPlane, account_id: str, *, as_of: str,
) -> tuple[EvidenceRef, ...]:
    """Read-only evidence pool the LLM's Job 2 (candidate divergences) may
    cite from -- contacts, cases, usage signals. Contacts carry no natural
    timestamp of their own (a static CRM profile record), so ``as_of`` is
    used as their ``observed_at`` (the state was observed as of this
    reconciliation run)."""

    refs: list[EvidenceRef] = []
    for contact in data_plane.crm.list_contacts(account_id):
        refs.append(EvidenceRef("crm", contact.contact_id, "role", as_of))
    for case in data_plane.crm.list_cases(account_id):
        refs.append(EvidenceRef("crm", case.case_id, "status", case.created_at))
    for signal in data_plane.telemetry.list_usage_signals(account_id):
        refs.append(EvidenceRef("telemetry", signal.signal_id, signal.metric_name, signal.observed_at))
    return tuple(refs)


@dataclass(frozen=True)
class Explanation:
    text: str
    disclaimer: str
    evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class CandidateDivergence:
    origin: str  # always "llm_hypothesis"
    claim: str
    confidence: str  # "low" | "medium" -- never "high"
    evidence: tuple[EvidenceRef, ...]
    disclaimer: str


@dataclass(frozen=True)
class ReconciliationResult:
    account_id: str
    deterministic_signals: tuple[DeterministicSignal, ...]
    explanation: Explanation
    candidate_divergences: tuple[CandidateDivergence, ...]


class ReconciliationContractError(ValueError):
    """Raised when the LLM's output violates this slot's contract (bad
    JSON, missing field, confidence out of range, an evidence reference
    not present in the supplied raw evidence pool)."""


class ReconciliationWriter(Protocol):
    def write(
        self,
        *,
        account_id: str,
        deterministic_signals: tuple[DeterministicSignal, ...],
        raw_evidence: tuple[EvidenceRef, ...],
    ) -> tuple[str, tuple[CandidateDivergence, ...]]: ...


def _evidence_ref_by_id(pool: tuple[EvidenceRef, ...]) -> dict[str, EvidenceRef]:
    return {ref.source_id: ref for ref in pool}


def _parse_and_validate(
    text: str, *, raw_evidence: tuple[EvidenceRef, ...],
) -> tuple[str, tuple[CandidateDivergence, ...]]:
    try:
        raw = json.loads(_extract_json_object(text))
    except json.JSONDecodeError as exc:
        raise ReconciliationContractError(f"invalid JSON: {exc}") from exc

    explanation_text = raw.get("explanation")
    if not isinstance(explanation_text, str) or not explanation_text.strip():
        raise ReconciliationContractError("explanation must be a non-empty string")

    candidates_raw = raw.get("candidate_divergences", ())
    if not isinstance(candidates_raw, list | tuple):
        raise ReconciliationContractError("candidate_divergences must be a list")
    if len(candidates_raw) > MAX_CANDIDATE_DIVERGENCES:
        # Enforced in code, not merely prompt-instructed (Decisions).
        candidates_raw = candidates_raw[:MAX_CANDIDATE_DIVERGENCES]

    by_id = _evidence_ref_by_id(raw_evidence)
    candidates: list[CandidateDivergence] = []
    for item in candidates_raw:
        claim = item.get("claim")
        confidence = item.get("confidence")
        if not isinstance(claim, str) or not claim.strip():
            raise ReconciliationContractError("candidate claim must be a non-empty string")
        if confidence not in ("low", "medium"):
            raise ReconciliationContractError(
                f"candidate confidence must be 'low' or 'medium', got {confidence!r}"
            )
        cited = []
        for ev in item.get("evidence", ()):
            source_id = ev.get("source_id")
            ref = by_id.get(source_id)
            if ref is None:
                raise ReconciliationContractError(
                    f"candidate cites source_id {source_id!r} not present in raw_evidence"
                )
            cited.append(ref)
        candidates.append(CandidateDivergence(
            origin="llm_hypothesis",
            claim=claim,
            confidence=confidence,
            evidence=tuple(cited),
            disclaimer=CANDIDATE_DISCLAIMER,
        ))
    return explanation_text, tuple(candidates)


@dataclass
class FixtureReconciliationWriter:
    """Deterministic, no-network writer for tests/fixture-mode runs."""

    explanation_text: str = "Fixture explanation: no live model configured."
    candidates: tuple[CandidateDivergence, ...] = ()

    def write(
        self,
        *,
        account_id: str,
        deterministic_signals: tuple[DeterministicSignal, ...],
        raw_evidence: tuple[EvidenceRef, ...],
    ) -> tuple[str, tuple[CandidateDivergence, ...]]:
        return self.explanation_text, self.candidates[:MAX_CANDIDATE_DIVERGENCES]


class AnthropicReconciliationWriter:
    """Live reconciliation slot. Mirrors slot_b.py's AnthropicReasonDraftWriter
    call pattern (same client/timeout/retry constants, same live model id
    reused per Decisions) -- not constructed by the offline battery."""

    model_id = LIVE_RECONCILIATION_MODEL_ID
    prompt_version = RECONCILIATION_PROMPT_VERSION

    def __init__(
        self,
        client=None,
        *,
        model_id: str | None = None,
        prompt_text: str | None = None,
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        if client is None:  # pragma: no cover - live lane
            from anthropic import Anthropic

            client = Anthropic(timeout=LIVE_TIMEOUT_S, max_retries=LIVE_MAX_RETRIES)
        self._client = client
        self.model_id = model_id or LIVE_RECONCILIATION_MODEL_ID
        self._prompt_text = prompt_text
        self._cost_tracker = cost_tracker

    def write(
        self,
        *,
        account_id: str,
        deterministic_signals: tuple[DeterministicSignal, ...],
        raw_evidence: tuple[EvidenceRef, ...],
    ) -> tuple[str, tuple[CandidateDivergence, ...]]:
        prompt = self._prompt_text or RECONCILIATION_PROMPT_PATH.read_text(encoding="utf-8")
        payload = {
            "account_id": account_id,
            "deterministic_signals": [
                {
                    "name": s.name,
                    "value": s.value,
                    "contribution": s.contribution,
                    "surfaced_by_lenses": list(s.surfaced_by_lenses),
                    "evidence": [
                        {"source": e.source, "source_id": e.source_id, "field": e.field, "observed_at": e.observed_at}
                        for e in s.evidence
                    ],
                }
                for s in deterministic_signals
            ],
            "raw_evidence": [
                {"source": e.source, "source_id": e.source_id, "field": e.field, "observed_at": e.observed_at}
                for e in raw_evidence
            ],
        }
        start = time.perf_counter()
        msg = self._client.messages.create(
            model=self.model_id,
            # 1500, not slot_b.py's 700: this response can include up to
            # MAX_CANDIDATE_DIVERGENCES candidates, each with its own
            # evidence list -- more structured output than Slot B's
            # reason+customer_draft shape. A truncated response is a
            # ReconciliationContractError (invalid JSON), not silently
            # accepted -- retry at the call site, don't just raise the cap
            # further without bound.
            max_tokens=1500,
            system=prompt,
            messages=[{"role": "user", "content": json.dumps(payload, sort_keys=True)}],
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        usage = getattr(msg, "usage", None)
        in_tok = getattr(usage, "input_tokens", None)
        out_tok = getattr(usage, "output_tokens", None)
        if self._cost_tracker is not None and in_tok is not None:
            self._cost_tracker.record(
                model_id=self.model_id,
                input_tokens=in_tok,
                output_tokens=out_tok or 0,
                latency_ms=latency_ms,
                account_id=account_id,
            )
        explanation_text, candidates = _parse_and_validate(
            _text_from_message(msg), raw_evidence=raw_evidence,
        )
        return explanation_text, candidates


def explain(
    data_plane: CustomerDataPlane,
    account_id: str,
    *,
    as_of: str,
    writer: ReconciliationWriter,
    snapshot_store: SnapshotStore | None = None,
) -> ReconciliationResult | None:
    """Full reconciliation: Tier-1 gathering + the guarded LLM slot
    (Job 1 explanation, Job 2 at-most-3 judge-eligible candidate
    divergences). Returns ``None`` when Tier-1 gathering itself returns
    ``None`` (missing account/CS data)."""

    signals = gather_signals(data_plane, account_id, as_of=as_of, snapshot_store=snapshot_store)
    if signals is None:
        return None

    raw_evidence = _raw_evidence_pool(data_plane, account_id, as_of=as_of)
    explanation_text, candidates = writer.write(
        account_id=account_id,
        deterministic_signals=signals,
        raw_evidence=raw_evidence,
    )
    explanation_evidence = tuple(
        ref for signal in signals for ref in signal.evidence
    )
    return ReconciliationResult(
        account_id=account_id,
        deterministic_signals=signals,
        explanation=Explanation(
            text=explanation_text,
            disclaimer=EXPLANATION_DISCLAIMER,
            evidence=explanation_evidence,
        ),
        candidate_divergences=candidates,
    )
