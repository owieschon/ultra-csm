"""Comparative customer-decision evaluation: the unchanged Ultra sweep
(``run_time_to_value_sweep`` behind the real ``ActionGate``) against a small,
independently implemented rules baseline, over 24 model-authored development
accounts (``eval/customer_outcome_cases.py``).

The job being evaluated: choose a justified customer action, internal
verification/escalation, hold, or no action from account facts available at
a specific time -- specifically, whether a claimed completed
engineering/onboarding change actually establishes the customer's objective.
A closed case, green health, or high activity alone does not prove success.
Source-reported objective completion stays source-reported; this harness
never claims causal impact.

Usage:

    PYTHONPATH=src:. python eval/customer_outcome_comparison.py \\
        --out-json /path/to/result.json --out-md /path/to/report.md

Both output paths must be given explicitly (no silent default write
location), and neither is overwritten if it already exists unless
``--force`` is passed.

This harness does not call any live LLM or connect to a real tenant; it uses
the existing deterministic fixture writer (``FixtureReasonDraftWriter``) and
an ``EphemeralCluster`` local Postgres for the real ``ActionGate``. It is not
a Pylon product benchmark -- it is a development-capability regression eval
comparing two policies against the same synthetic facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

_REPO = Path(__file__).resolve().parents[1]
_MIGRATIONS = _REPO / "migrations"

sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src"))

from eval.customer_outcome_cases import (  # noqa: E402
    AS_OF,
    CASE_REVISION,
    CASE_AUTHORSHIP,
    CASE_EXPOSURE,
    TENANT,
    DecisionPoint,
    Expectation,
    build_cases,
    build_data_plane,
    build_expectations,
)

Decision = Literal[
    "propose_customer_action", "internal_review", "escalate", "hold", "ambiguous"
]


# ---------------------------------------------------------------------------
# Normalized decision shape -- shared vocabulary both policies map into.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedDecision:
    account_id: str
    decision: Decision
    reason: str
    evidence_refs: tuple[str, ...]
    recipient: str | None
    draft_purpose: str | None
    unsupported: bool = False
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Baseline: an independently implemented rules policy over the SAME
# CustomerDataPlane read seams the sweep uses, and the same consent/identity
# boundary. It never imports or calls any ultra_csm.agent1 policy function.
# ---------------------------------------------------------------------------
#
# Published rules, in priority order, per resolved account:
#   1. Identity ambiguous (the same email resolves to more than one
#      account_id in the book) -> escalate. Never propose customer outreach.
#   2. Any open CRM case whose subject names a blocker ("block" substring)
#      -> escalate (verified internal blocker).
#   3. Any open, High-priority CTA -> escalate (internal specialist review).
#   4. Otherwise, derive objective_state from the account's success plans and
#      time-to-value milestones:
#        - "verified": every named objective has matching, dated milestone
#          completion no later than as_of. Exact-name matching is an explicit
#          fixture assumption; live source mappings remain unverified.
#        - "overdue": an unverified objective has a past plan/milestone deadline.
#        - "claimed_complete_unverified": source claims all plans complete,
#          but matching milestone evidence is absent.
#        - "in_progress": remaining objectives have no past deadline.
#        - "no_plan": no named objectives exist.
#   5. Map objective_state to an intervention:
#        verified + no open cases/CTAs           -> hold
#        verified + open cases/CTAs remain        -> internal_review
#        claimed_complete_unverified              -> internal_review
#        overdue                                  -> customer_action
#        in_progress, zero usage_signals           -> internal_review
#        in_progress, usage_signals present        -> hold
#        no_plan, no open cases/CTAs               -> hold
#        no_plan, open cases/CTAs remain           -> internal_review
#   6. "customer_action" only becomes propose_customer_action if at least
#      one contact on the account has consent_to_contact True; otherwise it
#      downgrades to internal_review. No-consent/ambiguous identity never
#      yields propose_customer_action.


def _has_blocker_case(cases) -> bool:
    return any(c.status == "Open" and "block" in c.subject.lower() for c in cases)


def _has_high_open_cta(ctas) -> bool:
    return any(c.status == "open" and c.priority == "High" for c in ctas)


def _day(value):
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _objective_state(success_plans, milestones, *, as_of_date: date) -> str:
    objectives = [(p, o) for p in success_plans for o in p.objectives]
    if not objectives:
        return "no_plan"
    unresolved = []
    for plan, objective in objectives:
        matches = [m for m in milestones if m.milestone == objective]
        if not any(m.achieved_at and _day(m.achieved_at) is not None
                   and _day(m.achieved_at) <= as_of_date for m in matches):
            unresolved.append((plan, matches))
    if not unresolved:
        return "verified"
    if all(p.status in {"complete", "achieved", "realized"} for p, _ in unresolved):
        return "claimed_complete_unverified"
    for plan, matches in unresolved:
        deadlines = [plan.target_date, *(m.expected_by for m in matches)]
        if any(_day(d) is not None and _day(d) < as_of_date for d in deadlines):
            return "overdue"
    return "in_progress"


def baseline_decide(
    plane, *, account_id: str, as_of: str, ambiguous: bool
) -> NormalizedDecision:
    as_of_date = date.fromisoformat(as_of[:10])
    contacts = plane.crm.list_contacts(account_id)
    cases = plane.crm.list_cases(account_id)
    ctas = plane.cs.list_ctas(account_id)
    plans = plane.cs.list_success_plans(account_id)
    milestones = plane.telemetry.list_ttv_milestones(account_id)
    usage_signals = [
        u for u in plane.telemetry.list_usage_signals(account_id)
        if _day(u.observed_at) is not None
        and 0 <= (as_of_date - _day(u.observed_at)).days <= 30
    ]
    consenting = [c for c in contacts if c.consent_to_contact]

    if ambiguous:
        return NormalizedDecision(
            account_id, "escalate",
            "baseline: identity resolves to more than one account for this contact email",
            (), None, None,
        )
    if _has_blocker_case(cases):
        return NormalizedDecision(
            account_id, "escalate",
            "baseline: open case names a verified activation blocker",
            tuple(c.case_id for c in cases if c.status == "Open"), None, None,
        )
    if _has_high_open_cta(ctas):
        return NormalizedDecision(
            account_id, "escalate",
            "baseline: open high-priority CTA requires internal specialist review",
            tuple(c.cta_id for c in ctas if c.status == "open" and c.priority == "High"), None, None,
        )

    state = _objective_state(plans, milestones, as_of_date=as_of_date)
    open_items = [c for c in cases if c.status == "Open"] + [c for c in ctas if c.status == "open"]

    if state == "verified":
        if open_items:
            return NormalizedDecision(account_id, "internal_review",
                                       "baseline: objective verified but open items remain", (), None, None)
        return NormalizedDecision(account_id, "hold", "baseline: objective verified, no open items", (), None, None)
    if state == "claimed_complete_unverified":
        return NormalizedDecision(account_id, "internal_review",
                                   "baseline: plan marked complete but no milestone confirms the objective",
                                   (), None, None)
    if state == "overdue":
        if consenting:
            return NormalizedDecision(account_id, "propose_customer_action",
                                       "baseline: plan objective overdue and unresolved", (),
                                       consenting[0].contact_id, "outcome_verification", )
        return NormalizedDecision(account_id, "internal_review",
                                   "baseline: plan objective overdue but no consenting contact", (), None, None)
    if state == "in_progress":
        if not usage_signals:
            return NormalizedDecision(account_id, "internal_review",
                                       "baseline: objective in progress with no telemetry evidence",
                                       (), None, None)
        return NormalizedDecision(account_id, "hold", "baseline: objective in progress, telemetry present",
                                   (), None, None)
    # no_plan
    if open_items:
        return NormalizedDecision(account_id, "internal_review",
                                   "baseline: no success plan, open items remain", (), None, None)
    return NormalizedDecision(account_id, "hold", "baseline: no success plan, no open items", (), None, None)


def run_baseline(plane, points: tuple[DecisionPoint, ...], *, as_of: str) -> dict[str, NormalizedDecision]:
    """Independently resolves identity ambiguity the same way the product
    contract does (``resolve_account_by_email``), without calling any Ultra
    policy function."""
    out: dict[str, NormalizedDecision] = {}
    for p in points:
        for contact in p.contacts:
            resolution = plane.crm.resolve_account_by_email(contact.email)
            ambiguous = resolution.state == "ambiguous"
            out[p.account_id] = baseline_decide(
                plane, account_id=p.account_id, as_of=as_of, ambiguous=ambiguous
            )
            break
    return out


# ---------------------------------------------------------------------------
# Ultra normalization -- reads only real CSMWorkItem/escalation fields.
# ---------------------------------------------------------------------------


def normalize_ultra(sweep_result, account_id: str) -> NormalizedDecision:
    for item in sweep_result.escalations:
        if item.account_id == account_id or account_id in item.candidate_account_ids:
            return NormalizedDecision(
                account_id, "escalate", item.reason,
                tuple(e.source_id for e in item.evidence), None, None,
            )
    for item in sweep_result.work_items:
        if item.account_id != account_id:
            continue
        recipient = item.recipient_name
        purpose = None
        if item.work_packet is not None and item.work_packet.prepared_artifact is not None:
            purpose = item.work_packet.prepared_artifact.artifact_type
        if item.disposition == "propose_customer_action":
            if item.customer_draft is None or item.proposal is None:
                return NormalizedDecision(
                    account_id, "ambiguous",
                    f"ultra: disposition=propose_customer_action but no draft/proposal artifact "
                    f"({item.reason})",
                    tuple(e.source_id for e in item.evidence), recipient, purpose, unsupported=True,
                )
            return NormalizedDecision(
                account_id, "propose_customer_action", item.reason,
                tuple(e.source_id for e in item.evidence), recipient, purpose,
            )
        if item.disposition in ("internal_review", "escalate"):
            return NormalizedDecision(
                account_id, item.disposition, item.reason,
                tuple(e.source_id for e in item.evidence), recipient, purpose,
            )
        return NormalizedDecision(
            account_id, "ambiguous", f"ultra: unrecognized disposition {item.disposition!r}",
            tuple(e.source_id for e in item.evidence), recipient, purpose, unsupported=True,
        )
    if account_id in sweep_result.swept_accounts:
        return NormalizedDecision(account_id, "hold", "ultra: account scanned, no work item emitted", (), None, None)
    return NormalizedDecision(
        account_id, "ambiguous",
        "ultra: account not present in swept_accounts -- cannot verify it was scanned before crediting hold",
        (), None, None, unsupported=True,
    )


# ---------------------------------------------------------------------------
# Forbidden-consequence checks -- apply identically to both policies.
# ---------------------------------------------------------------------------


def forbidden_violations(point: DecisionPoint, exp: Expectation, decision: NormalizedDecision) -> tuple[str, ...]:
    violations = []
    if decision.decision in exp.forbidden_decisions:
        violations.append(f"decision {decision.decision!r} is in this case's forbidden set")
    consenting = any(c.consent_to_contact for c in point.contacts)
    if decision.decision == "propose_customer_action" and not consenting:
        violations.append("propose_customer_action emitted for an account with no consenting contact")
    if decision.decision == "propose_customer_action":
        eligible = {c.contact_id for c in point.contacts
                    if c.account_id == point.account_id and c.consent_to_contact}
        if decision.recipient not in eligible:
            violations.append("selected recipient is not an eligible consenting account contact")
        if exp.required_customer_purpose and decision.draft_purpose != exp.required_customer_purpose:
            violations.append("customer action does not preserve required outcome-verification purpose")
    return tuple(violations)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO, text=True
        ).strip()
    except Exception:
        return "unknown"


def _case_digest(points: tuple[DecisionPoint, ...], expectations: dict[str, Expectation]) -> dict:
    return {
        "cases_sha256": _sha256([asdict(p) for p in points]),
        "expectations_sha256": _sha256({k: asdict(v) for k, v in expectations.items()}),
        "case_count": len(points),
        "story_count": len({p.story for p in points}),
        "revision": CASE_REVISION,
    }


def write_freeze_receipt(path: Path, points, expectations, *, force: bool) -> dict:
    digest = _case_digest(points, expectations)
    digest["source_sha"] = _git_sha()
    digest["frozen_at"] = datetime.now(timezone.utc).isoformat()
    digest["authorship"] = (
        "model-authored, controller-guided, repository-exposed development "
        "challenge cases -- not an untouched holdout or independent human labels"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        existing = json.loads(path.read_text())
        if any(existing.get(k) != digest[k] for k in ("cases_sha256", "expectations_sha256")):
            raise RuntimeError(
                "customer-outcome case fixtures changed since the freeze receipt was "
                f"written at {path}; case definitions must be frozen before an evaluated run"
            )
        return existing
    with path.open("w" if force else "x") as f:
        json.dump(digest, f, indent=2, sort_keys=True)
    return digest


def _source_provenance():
    paths = ["eval/customer_outcome_cases.py", "eval/customer_outcome_comparison.py"]
    paths += [str(p.relative_to(_REPO)) for p in sorted((_REPO / "src/ultra_csm").rglob("*.py"))]
    digests = {p: hashlib.sha256((_REPO / p).read_bytes()).hexdigest() for p in paths}
    return {"git_sha": _git_sha(), "files_sha256": digests}


def _source_facts(point):
    data = asdict(point)
    for key in ("story", "point", "changed_fields", "category", "noise_variant"):
        data.pop(key)
    return data


def _changed_paths(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for k in sorted(a.keys() | b.keys())
                for p in _changed_paths(a.get(k), b.get(k), f"{prefix}.{k}".strip("."))]
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [prefix]
        return [p for i, (x, y) in enumerate(zip(a, b))
                for p in _changed_paths(x, y, f"{prefix}[{i}]")]
    return [] if a == b else [prefix]


def _pair_results(cases):
    out = []
    for story in sorted({c["story"] for c in cases}):
        a, b = sorted((c for c in cases if c["story"] == story), key=lambda c: c["point"])
        out.append({
            "story": story, "noise_pair": b["noise_variant"],
            "actual_source_changes": _changed_paths(a["source_facts"], b["source_facts"]),
            "comparison_scope": "paired snapshots; generated identities also differ",
            "baseline_decision_changed": a["baseline"]["decision"] != b["baseline"]["decision"],
            "ultra_decision_changed": a["ultra"]["decision"] != b["ultra"]["decision"],
            "ultra_purpose_changed": a["ultra"]["draft_purpose"] != b["ultra"]["draft_purpose"],
        })
    return out


def run_comparison(*, as_of: str = AS_OF) -> dict:
    from ultra_csm.governance import ActionGate, FixtureVerdictSource
    from ultra_csm.platform import boot_seeded_cluster
    from ultra_csm.value_model import load_value_model_config

    points = build_cases()
    expectations = build_expectations(points)
    plane = build_data_plane(points)
    baseline_by_account = run_baseline(plane, points, as_of=as_of)

    from ultra_csm.agent1 import FixtureReasonDraftWriter
    class CapturingWriter(FixtureReasonDraftWriter):
        def __init__(self):
            self.requests = {}
        def write(self, request):
            self.requests[request.account_id] = request
            return super().write(request)
    writer = CapturingWriter()
    cluster_error = None
    proposal_count = 0
    sweep_result = None
    try:
        with boot_seeded_cluster(_MIGRATIONS, limit=200) as (cluster, _dsn):
            import psycopg

            from tests._govhelpers import CLOCK, setup_roster
            from ultra_csm.agent1.sweep import run_time_to_value_sweep

            from ultra_csm.data_plane.fixtures import det_id

            db_tenant = det_id("outcome-comparison-db-tenant")
            db_agent = det_id("outcome-comparison-db-agent")
            conn = psycopg.connect(**cluster.dsn(user="app_runtime"))
            try:
                conn.execute("BEGIN")
                orch, _authority = setup_roster(conn, tenant=db_tenant, seed_actor=db_agent)
                gate = ActionGate(
                    conn, tenant_id=db_tenant, actor_principal_id=orch,
                    verdict_source=FixtureVerdictSource(), now=CLOCK,
                )
                sweep_result = run_time_to_value_sweep(
                    plane, TENANT, gate, sweep_principal_id=orch, as_of=as_of,
                    value_model_config=load_value_model_config(),
                    reason_draft_writer=writer,
                )
                from ultra_csm.platform.db import session
                with session(conn, tenant_id=db_tenant, actor_id=orch) as cur:
                    cur.execute("SELECT count(*) FROM action_proposal")
                    proposal_count = cur.fetchone()[0]
            finally:
                conn.rollback()
                conn.close()
    except Exception as exc:  # EphemeralCluster unavailable in this sandbox
        cluster_error = f"{type(exc).__name__}: {exc}"

    cases_out = []
    for p in points:
        exp = expectations[p.account_id]
        baseline = baseline_by_account[p.account_id]
        if sweep_result is not None:
            ultra = normalize_ultra(sweep_result, p.account_id)
            request = writer.requests.get(p.account_id)
            item = next((i for i in sweep_result.work_items if i.account_id == p.account_id), None)
            if request is not None:
                matches = [c for c in p.contacts if c.email == request.contact_email]
                ultra = replace(ultra,
                    recipient=matches[0].contact_id if len(matches) == 1 else None,
                    draft_purpose=request.decision_purpose,
                    raw={"action": item.recommended_action if item else None,
                         "motion": item.motion if item else None,
                         "disposition": item.disposition if item else None,
                         "customer_draft": item.customer_draft if item else None})
        else:
            ultra = NormalizedDecision(
                p.account_id, "ambiguous",
                f"ultra sweep did not run: {cluster_error}", (), None, None, unsupported=True,
            )
        baseline_violations = forbidden_violations(p, exp, baseline)
        ultra_violations = forbidden_violations(p, exp, ultra)
        cases_out.append({
            "story": p.story,
            "point": p.point,
            "category": p.category,
            "noise_variant": p.noise_variant,
            "account_id": p.account_id,
            "changed_fields": p.changed_fields,
            "allowed_decisions": exp.allowed_decisions,
            "forbidden_decisions": exp.forbidden_decisions,
            "rationale": exp.rationale,
            "required_customer_purpose": exp.required_customer_purpose,
            "source_facts": _source_facts(p),
            "baseline": asdict(baseline),
            "ultra": asdict(ultra),
            "baseline_in_allowed_set": baseline.decision in exp.allowed_decisions,
            "ultra_in_allowed_set": ultra.decision in exp.allowed_decisions,
            "baseline_forbidden_violations": baseline_violations,
            "ultra_forbidden_violations": ultra_violations,
            "disagreement": baseline.decision != ultra.decision,
        })

    metrics = {
        "case_count": len(cases_out),
        "baseline_in_allowed_set": sum(c["baseline_in_allowed_set"] for c in cases_out),
        "ultra_in_allowed_set": sum(c["ultra_in_allowed_set"] for c in cases_out),
        "baseline_forbidden_violation_count": sum(len(c["baseline_forbidden_violations"]) for c in cases_out),
        "ultra_forbidden_violation_count": sum(len(c["ultra_forbidden_violations"]) for c in cases_out),
        "disagreement_count": sum(c["disagreement"] for c in cases_out),
        "ultra_unsupported_count": sum(c["ultra"]["unsupported"] for c in cases_out),
        "ultra_sweep_ran": sweep_result is not None,
        "persisted_proposal_count": proposal_count,
        "ultra_sweep_error": cluster_error,
    }

    return {
        "artifact": "customer_outcome_comparison",
        "label": "synthetic development comparison; no live model, host, causal impact or platform-breadth claim",
        "authorship": CASE_AUTHORSHIP,
        "exposure": CASE_EXPOSURE,
        "source_provenance": _source_provenance(),
        "pairs": _pair_results(cases_out),
        "as_of": as_of,
        "tenant": TENANT,
        "source_sha": _git_sha(),
        "case_digest": _case_digest(points, expectations),
        "metrics": metrics,
        "cases": cases_out,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_markdown(result: dict) -> str:
    m = result["metrics"]
    lines = [
        "# Customer-outcome comparison: Ultra sweep vs. rules baseline",
        "",
        f"as_of: `{result['as_of']}`  |  source SHA: `{result['source_sha']}`  |  "
        f"case digest: `{result['case_digest']['cases_sha256'][:12]}`",
        "",
        result["label"],
        "",
        result["authorship"],
        "",
        result["exposure"],
        "",
        "## Metrics",
        "",
        f"- cases: {m['case_count']}",
        f"- baseline decisions within the declared allowed set: {m['baseline_in_allowed_set']}/{m['case_count']}",
        f"- ultra decisions within the declared allowed set: {m['ultra_in_allowed_set']}/{m['case_count']}",
        f"- baseline forbidden-consequence violations: {m['baseline_forbidden_violation_count']}",
        f"- ultra forbidden-consequence violations: {m['ultra_forbidden_violation_count']}",
        f"- disagreements between baseline and ultra: {m['disagreement_count']}",
        f"- ultra unsupported/ambiguous classifications: {m['ultra_unsupported_count']}",
        f"- ultra sweep ran: {m['ultra_sweep_ran']}"
        + (f" (error: {m['ultra_sweep_error']})" if not m["ultra_sweep_ran"] else ""),
        "",
        "## Cases",
        "",
        "| story | pt | category | changed field(s) | allowed | baseline | ultra | violation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in result["cases"]:
        viol = []
        if c["baseline_forbidden_violations"]:
            viol.append("baseline:" + ";".join(c["baseline_forbidden_violations"]))
        if c["ultra_forbidden_violations"]:
            viol.append("ultra:" + ";".join(c["ultra_forbidden_violations"]))
        lines.append(
            f"| {c['story']} | {c['point']} | {c['category']} | "
            f"{', '.join(c['changed_fields'])} | {', '.join(c['allowed_decisions'])} | "
            f"{c['baseline']['decision']} | {c['ultra']['decision']} | "
            f"{'; '.join(viol) if viol else '-'} |"
        )
    lines.append("")
    lines.append("## Paired decisions")
    lines.append("")
    for pair in result["pairs"]:
        lines.append(f"- {pair['story']}: baseline decision changed={pair['baseline_decision_changed']}; "
                     f"Ultra decision changed={pair['ultra_decision_changed']}; noise pair={pair['noise_pair']}.")
    lines.append("")
    lines.append("Full source-field deltas, including generated identity changes, are in the JSON report.")
    lines.append("")
    lines.append("## Per-case evidence")
    lines.append("")
    for c in result["cases"]:
        lines.append(f"### {c['story']}/{c['point']} ({c['account_id']})")
        lines.append("")
        lines.append(f"- rationale: {c['rationale']}")
        facts = c["source_facts"]
        lines.append(f"- source plan states: {[(p['objectives'], p['status'], p['target_date']) for p in facts['success_plans']]}")
        lines.append(f"- source milestones: {[(m['milestone'], m['achieved_at']) for m in facts['milestones']]}")
        lines.append(f"- Ultra purpose: {c['ultra']['draft_purpose']}; evidence references: {c['ultra']['evidence_refs']}")
        lines.append(f"- baseline: {c['baseline']['decision']} -- {c['baseline']['reason']}")
        lines.append(f"- ultra: {c['ultra']['decision']} -- {c['ultra']['reason']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-md", required=True, type=Path)
    parser.add_argument("--freeze-receipt", type=Path, default=None,
                         help="Path to a private freeze receipt to write/verify before running.")
    parser.add_argument("--first-results", type=Path, default=None,
                         help="Exclusive-create path to preserve the first full result set.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing --out-json/--out-md.")
    args = parser.parse_args(argv)

    if not args.force:
        for p in (args.out_json, args.out_md):
            if p.exists():
                print(f"refusing to overwrite existing {p} without --force", file=sys.stderr)
                return 2

    points = build_cases()
    expectations = build_expectations(points)
    if args.freeze_receipt is not None:
        write_freeze_receipt(args.freeze_receipt, points, expectations, force=False)

    result = run_comparison()

    if args.first_results is not None and not args.first_results.exists():
        args.first_results.parent.mkdir(parents=True, exist_ok=True)
        with open(args.first_results, "x") as f:
            json.dump(result, f, indent=2, sort_keys=True, default=str)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(render_markdown(result))

    m = result["metrics"]
    print(
        f"cases={m['case_count']} baseline_allowed={m['baseline_in_allowed_set']} "
        f"ultra_allowed={m['ultra_in_allowed_set']} baseline_violations={m['baseline_forbidden_violation_count']} "
        f"ultra_violations={m['ultra_forbidden_violation_count']} sweep_ran={m['ultra_sweep_ran']}"
    )
    return 0 if m["ultra_sweep_ran"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
