"""Lane B keystone: prove live semantic quality on real tenant output.

Builds a small in-memory book over corpus B (Salesforce) account NAMES
fetched live, generates real Slot B drafts with the live model
(AnthropicReasonDraftWriter), and scores them with the validated N-run
(cot@N) judge (AnthropicQualityJudge, docs/DECISION_LOG.md). This is a
manually-invoked, credentialed, non-CI script -- it requires
ANTHROPIC_API_KEY and writes eval/gold/live_semantic_quality.json, the
evidence artifact `eval.judge_validation.live_semantic_quality_status`
derives its `proven` claim from.

Real Salesforce numeric record ids are NEVER used as the join key here or
persisted to the artifact -- only the account NAME (already-public seeded
test data) and a synthetic opaque id. There is no live CS-platform or
product-telemetry connector in this architecture (Program 4's
cross-system-beat precedent), so that evidence is synthetic; the book_source
field on the artifact states this explicitly.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_nrun import aggregate
from eval.judge_validation import live_semantic_quality_status
from ultra_csm.agent1 import build_reason_draft_request_for_account
from ultra_csm.agent1.slot_b import AnthropicReasonDraftWriter, SLOT_B_PROMPT_VERSION
from ultra_csm.data_plane.contracts import (
    CTA,
    AdoptionSummary,
    CRMAccount,
    CRMContact,
    CSCompany,
    CustomerDataPlane,
    HealthScore,
    SuccessPlan,
    TimeToValueMilestone,
    resolve_candidates,
)

ARTIFACT_PATH = Path(__file__).with_name("gold") / "live_semantic_quality.json"
SCHEMA_VERSION = 1
DEFAULT_RUNS_PER_CANDIDATE = 5
AS_OF = "2026-07-03"

# Real corpus B (Salesforce) account NAMES fetched live 2026-07-03 (UCSM-P3E
# seed corpus, see docs/PROGRAM_REPORT_5.md); the real numeric Salesforce ids
# are never used here -- the opaque_id below is the in-memory join key.
DEFAULT_BOOK = (
    {
        "opaque_id": "corpus-b-live-1",
        "name": "UCSM-P3E-D1-A001 Volume Account 1",
        "owner_id": "csm-live-1",
        "consented_contact": True,
    },
    {
        "opaque_id": "corpus-b-live-2",
        "name": "UCSM-P3E-D3-A001 Sparse Account 1",
        "owner_id": "csm-live-2",
        "consented_contact": False,
    },
)


class _BookCRM:
    def __init__(self, accounts, contacts):
        self._accounts = {a.account_id: a for a in accounts}
        self._contacts = contacts

    def list_accounts(self, *, tenant_id=None):
        return list(self._accounts.values())

    def get_account(self, account_id):
        return self._accounts.get(account_id)

    def list_contacts(self, account_id):
        return [c for c in self._contacts if c.account_id == account_id]

    def list_cases(self, account_id):
        return []

    def list_opportunities(self, account_id):
        return []

    def resolve_account_by_email(self, email):
        for c in self._contacts:
            if c.email.lower() == email.lower():
                return resolve_candidates([c.account_id])
        return resolve_candidates([])

    def log_activity(self, account_id, *, channel, direction, summary, idempotency_key):
        return "n/a"


class _BookCS:
    def __init__(self, companies, healths, adoptions, ctas, plans):
        self._companies = {c.company_id: c for c in companies}
        self._healths = {h.account_id: h for h in healths}
        self._adoptions = {a.account_id: a for a in adoptions}
        self._ctas = ctas
        self._plans = plans

    def get_company(self, account_id):
        return self._companies.get(account_id)

    def get_health_score(self, account_id):
        return self._healths.get(account_id)

    def get_adoption_summary(self, account_id):
        return self._adoptions.get(account_id)

    def list_ctas(self, account_id, *, status=None):
        items = [c for c in self._ctas if c.account_id == account_id]
        if status is not None:
            items = [c for c in items if c.status == status]
        return items

    def list_success_plans(self, account_id):
        return [p for p in self._plans if p.account_id == account_id]


class _BookTelemetry:
    def __init__(self, milestones):
        self._milestones = milestones

    def list_entitlements(self, account_id):
        return []

    def list_usage_signals(self, account_id, *, metric_name=None, since=None, until=None):
        return []

    def list_ttv_milestones(self, account_id):
        return [m for m in self._milestones if m.account_id == account_id]


def build_live_book_plane(book=DEFAULT_BOOK) -> CustomerDataPlane:
    accounts, contacts, companies, healths, adoptions, ctas, plans, milestones = (
        [], [], [], [], [], [], [], []
    )
    for row in book:
        aid = row["opaque_id"]
        accounts.append(CRMAccount(
            account_id=aid, name=row["name"], owner_id=row["owner_id"], industry="Manufacturing",
        ))
        if row["consented_contact"]:
            contacts.append(CRMContact(
                contact_id=f"{aid}-contact-1", account_id=aid,
                email=f"{aid}@example.test", name="Ops Lead", role="ops", title="Ops Lead",
                consent_to_contact=True,
            ))
        companies.append(CSCompany(
            company_id=aid, name=row["name"], industry="Manufacturing",
            arr_cents=4_500_000, lifecycle_stage="onboarding", status="active",
            original_contract_date="2026-05-01", renewal_date="2027-05-01",
            csm_owner_id=row["owner_id"], current_score=None,
        ))
        healths.append(HealthScore(
            account_id=aid, score=52.0, band="yellow",
            drivers=("live_semantic_quality_proof",), measured_at=AS_OF,
        ))
        adoptions.append(AdoptionSummary(
            account_id=aid, active_users=2, licensed_users=8,
            active_assets=1, entitled_assets=4, adoption_rate=0.25,
            underused_capabilities=("routing",), measured_at=AS_OF,
        ))
        ctas.append(CTA(
            cta_id=f"{aid}-cta-1", account_id=aid, reason="Activation risk",
            priority="high", status="open", due_date="2026-07-10", owner_id=row["owner_id"],
        ))
        plans.append(SuccessPlan(
            plan_id=f"{aid}-plan-1", account_id=aid, status="in_progress",
            objectives=("Activate purchased routing capability",), target_date="2026-07-15",
        ))
        milestones.append(TimeToValueMilestone(
            account_id=aid, milestone="Kickoff activation review",
            expected_by="2026-06-20", achieved_at=None,
            evidence_signal_ids=(f"{aid}-signal-1",),
        ))

    return CustomerDataPlane(
        crm=_BookCRM(accounts, contacts),
        cs=_BookCS(companies, healths, adoptions, ctas, plans),
        telemetry=_BookTelemetry(milestones),
    )


def build_live_semantic_quality_artifact(
    *,
    book=DEFAULT_BOOK,
    runs_per_candidate: int = DEFAULT_RUNS_PER_CANDIDATE,
    writer: AnthropicReasonDraftWriter | None = None,
    judge: AnthropicQualityJudge | None = None,
) -> dict[str, Any]:
    plane = build_live_book_plane(book)
    writer = writer or AnthropicReasonDraftWriter()
    judge = judge or AnthropicQualityJudge(reasoning=True)

    candidates = []
    for row in book:
        aid = row["opaque_id"]
        action = "draft_customer_outreach" if row["consented_contact"] else "recommend_next_best_action"
        request = build_reason_draft_request_for_account(
            plane, "live-semantic-quality-tenant", aid, as_of=AS_OF, action=action,
        )
        if request is None:
            raise RuntimeError(f"no Slot B request built for book row {aid}")
        output = writer.write(request)

        request_dict = asdict(request)
        request_dict["prompt_version"] = SLOT_B_PROMPT_VERSION
        output_dict = asdict(output)

        vectors = [judge.score_output(request_dict, output_dict) for _ in range(runs_per_candidate)]
        agg = aggregate(vectors)

        candidates.append({
            "candidate_id": aid,
            "disposition": request.disposition,
            "customer_contact_allowed": request.customer_contact_allowed,
            "request": request_dict,
            "output": output_dict,
            "runs": vectors,
            "agg": agg,
        })

    artifact = {
        "artifact": "live_semantic_quality_csm",
        "schema_version": SCHEMA_VERSION,
        "generated_by": "eval.live_semantic_quality_csm",
        "as_of": AS_OF,
        "draft_model_id": writer.model_id,
        "judge_model_id": judge.model_id,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_reasoning": judge.reasoning,
        "runs_per_candidate": runs_per_candidate,
        "book_source": (
            "Real corpus B (Salesforce) account NAMES fetched live (UCSM-P3E seed "
            "corpus); CS-platform/telemetry evidence is synthetic (no live "
            "CS-platform/telemetry connector exists in this architecture, matching "
            "Program 4's cross-system-beat precedent). Real Salesforce numeric ids "
            "are never persisted -- opaque ids are the join key."
        ),
        "candidates": candidates,
    }
    return artifact


def write_live_semantic_quality_artifact(
    output_path: Path = ARTIFACT_PATH,
    *,
    runs_per_candidate: int = DEFAULT_RUNS_PER_CANDIDATE,
) -> dict[str, Any]:
    artifact = build_live_semantic_quality_artifact(runs_per_candidate=runs_per_candidate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, sort_keys=True, indent=2), encoding="utf-8")
    # Recompute the claim boundary against the artifact as actually persisted,
    # so the embedded claim can never drift from what a reader loads from disk.
    artifact["claim_boundary"] = live_semantic_quality_status(live_path=output_path)
    output_path.write_text(json.dumps(artifact, sort_keys=True, indent=2), encoding="utf-8")
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_CANDIDATE)
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)

    artifact = write_live_semantic_quality_artifact(
        Path(args.output), runs_per_candidate=args.runs,
    )
    claim = artifact["claim_boundary"]
    print(f"live semantic quality: proven={claim['proven']} failures={claim['failures']}")
    print(f"artifact -> {args.output}")
    return 0 if claim["proven"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
