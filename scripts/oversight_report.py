"""Render the oversight evidence pack from the ledgers the system already keeps.

This is a RENDERER: it loads persisted ledgers/artifacts, groups and counts them,
and writes one machine-readable JSON + one human-readable Markdown report. It
computes no new metrics, mutates nothing, and imports no gate/database write
surface. Evidence classes with no persisted source are listed in the mandatory
"Not instrumented" section — never rendered as implicitly satisfied.

Same-inputs -> byte-identical outputs (no wall-clock reads).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ultra_csm.governance.authorizer import ROLE_PERMISSIONS
from ultra_csm.governance.csm_actions import CSM_ACTION_SPECS

ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "demo_state" / "oversight_report.json"
MD_OUT = ROOT / "demo_state" / "oversight_report.md"

DISCLAIMER = (
    "This report demonstrates that the system's ledgers contain the evidence "
    "classes an oversight regime requires. It is not a compliance assessment "
    "and not legal advice."
)

SOURCES = {
    "verdict_ledger": "eval/autonomy_verdict_ledger.jsonl",
    "commit_audit": "demo_state/commit_audit.jsonl",
    "operator_events": "demo_state/quality_breaker/operator_events.jsonl",
    "quality_artifact": "demo_state/quality_breaker/red_quality_artifact.json",
    "tick_ledger": "demo_state/tick_demo/tick_ledger.jsonl",
    "precedence_battery": "eval/precedence_battery.json",
    "quality_status": "eval/gold/slot_b_quality_status.json",
    "judge_agreement": "eval/gold/judge_agreement.json",
    "autonomy_report": "eval/autonomy_report.json",
}

NOT_INSTRUMENTED = (
    "Reviewer response-time SLAs: verdict rows carry proposed_at/verdict_at, but no "
    "SLA target or breach ledger exists.",
    "Second-reviewer / dual-control events: one human principal per verdict; no "
    "dual-approval record even for tier-3 release conditions that name dual control.",
    "Principal-level separation-of-duties runtime proof: the gate database enforces "
    "propose!=approve (migration 0004 separation-of-duties trigger) and its rows carry "
    "actor/human principal ids, but the file ledgers this report renders do not; the "
    "query-level proof requires the database, so it is not claimed here.",
    "Held-action event journal persistence: precedence hold/release/override events are "
    "evaluated per sweep and proven in eval/precedence_battery.json, but no cumulative "
    "hold-event JSONL is persisted outside the sweep runtime.",
    "Appeal / escalation workflow: denied proposals produce no escalation records.",
    "Verdict rationale coverage: the rationale field is optional and sparsely populated.",
    "Reviewer workload distribution: no queue-depth or per-reviewer pending snapshots.",
)


def build_oversight_report(root: Path = ROOT) -> dict[str, Any]:
    verdicts = _jsonl(root, SOURCES["verdict_ledger"])
    commits = _jsonl(root, SOURCES["commit_audit"])
    operator_events = _jsonl(root, SOURCES["operator_events"])
    ticks = _jsonl(root, SOURCES["tick_ledger"])
    quality_artifact = _json(root, SOURCES["quality_artifact"])
    precedence = _json(root, SOURCES["precedence_battery"])
    quality_status = _json(root, SOURCES["quality_status"])
    autonomy = _json(root, SOURCES["autonomy_report"])

    return {
        "artifact": "oversight_evidence_pack",
        "generated_by": "scripts.oversight_report",
        "disclaimer": DISCLAIMER,
        "claim_boundary": {
            "sim": True,
            "live": False,
            "evidence_record_not_certification": True,
            "renders_persisted_ledgers_only": True,
        },
        "sources": SOURCES,
        "sections": {
            "1_human_oversight_events": _human_oversight(verdicts, commits, operator_events),
            "2_separation_of_duties": _separation_of_duties(),
            "3_authority_boundaries": _authority_boundaries(verdicts),
            "4_suppression_and_release": _suppression_release(ticks, precedence),
            "5_degradation_honesty": _degradation(quality_artifact, operator_events),
            "6_quality_measurement": _quality_measurement(quality_status, quality_agreement=_json(root, SOURCES["judge_agreement"])),
            "7_autonomy_provenance": _autonomy(autonomy),
            "8_not_instrumented": list(NOT_INSTRUMENTED),
        },
    }


def _human_oversight(verdicts: list[dict], commits: list[dict], operator_events: list[dict]) -> dict:
    by_action: dict[str, Counter] = {}
    tiers: dict[str, set[int]] = {}
    for v in verdicts:
        action = str(v.get("action_type"))
        by_action.setdefault(action, Counter())[str(v.get("verdict"))] += 1
        tiers.setdefault(action, set()).add(int(v.get("autonomy_tier", 0)))
    events = [
        {
            "proposal_id": v.get("proposal_id"),
            "action_type": v.get("action_type"),
            "autonomy_tier": v.get("autonomy_tier"),
            "verdict": v.get("verdict"),
            "verdict_reason": v.get("verdict_reason"),
            "proposed_at": v.get("proposed_at"),
            "verdict_at": v.get("verdict_at"),
        }
        for v in verdicts
    ]
    receipts = [
        {
            "receipt_id": (c.get("receipt") or {}).get("receipt_id"),
            "proposal_id": (c.get("receipt") or {}).get("proposal_id"),
            "action": (c.get("receipt") or {}).get("action"),
            "payload_sha256": (c.get("receipt") or {}).get("payload_sha256"),
            "target": (c.get("receipt") or {}).get("target"),
            "source": c.get("source"),
        }
        for c in commits
        if c.get("event_type") == "outbound_committed"
    ]
    return {
        "verdict_events": events,
        "verdict_counts_by_action": {a: dict(sorted(c.items())) for a, c in sorted(by_action.items())},
        "tiers_observed_by_action": {a: sorted(t) for a, t in sorted(tiers.items())},
        "committed_outbound_receipts": receipts,
        "operator_acknowledgements": operator_events,
        "row_refs": "verdict rows -> eval/autonomy_verdict_ledger.jsonl (proposal_id); "
        "receipts -> demo_state/commit_audit.jsonl (receipt_id, payload_sha256); "
        "operator events -> demo_state/quality_breaker/operator_events.jsonl (event_id)",
    }


def _separation_of_duties() -> dict:
    proposer_permissions = sorted(
        perm for perm, role in ROLE_PERMISSIONS.items() if role == "cs_orchestrator"
    )
    approver_permissions = sorted(
        perm for perm, role in ROLE_PERMISSIONS.items() if role != "cs_orchestrator"
    )
    return {
        "design": {
            "proposing_role": "cs_orchestrator (agent principals)",
            "proposing_role_permissions": proposer_permissions,
            "approving_roles": approver_permissions
            and {"order_confirm_authority": approver_permissions},
            "enforcement": (
                "verdicts require a human principal; the gate database rejects a "
                "verdict whose human principal equals the proposal's actor principal "
                "(migration 0004 separation-of-duties trigger)"
            ),
        },
        "runtime_proof": (
            "NOT RENDERED HERE: the file ledgers carry no principal ids, so the "
            "query-level proof lives behind the gate database — see section 8."
        ),
    }


def _authority_boundaries(verdicts: list[dict]) -> dict:
    taxonomy = [
        {
            "action": spec.action,
            "autonomy_tier": spec.autonomy_tier,
            "required_permission": spec.required_permission,
            "release_condition": spec.release_condition,
            "customer_affecting": spec.customer_affecting,
        }
        for spec in (
            CSM_ACTION_SPECS[name] for name in sorted(CSM_ACTION_SPECS)
        )
    ]
    auto_audit = sorted(
        {
            str(v.get("proposal_id"))
            for v in verdicts
            if v.get("verdict_reason") == "auto_internal_ok"
        }
    )
    return {
        "action_taxonomy": taxonomy,
        "auto_executing": {
            "condition": "autonomy_tier 1 / release_condition auto_internal_only "
            "(internal-only, never customer-affecting)",
            "audit_trail_rows": auto_audit,
        },
        "human_verdict_required": sorted(
            spec["action"] for spec in taxonomy if spec["autonomy_tier"] >= 2
        ),
    }


def _suppression_release(ticks: list[dict], precedence: dict | None) -> dict:
    suppressions = [
        {
            "as_of": t.get("as_of"),
            "trigger_name": s.get("trigger_name"),
            "account_id": s.get("account_id"),
            "reason": s.get("reason"),
            "condition_instance": s.get("condition_instance"),
        }
        for t in ticks
        for s in t.get("suppressions", [])
    ]
    reasons = Counter(str(s["reason"]) for s in suppressions)
    battery = None
    if precedence:
        battery = {
            "artifact": precedence.get("artifact"),
            "score": precedence.get("score"),
            "hard_ok": precedence.get("hard_ok"),
            "cases": [
                {"case_id": c.get("case_id"), "passed": c.get("passed")}
                for c in precedence.get("cases", [])
            ],
            "measurement_scope": precedence.get("measurement_scope"),
        }
    return {
        "trigger_suppressions": suppressions,
        "suppression_reason_counts": dict(sorted(reasons.items())),
        "hold_release_rederivation_proof": battery,
        "row_refs": "suppressions -> demo_state/tick_demo/tick_ledger.jsonl "
        "(condition_instance); hold/release cases -> eval/precedence_battery.json (case_id)",
    }


def _degradation(quality_artifact: dict | None, operator_events: list[dict]) -> dict:
    return {
        "quality_breaker_artifact": quality_artifact,
        "operator_reset_events": [
            e for e in operator_events if e.get("event_type") == "quality_breaker_reset"
        ],
        "row_refs": "breaker state -> demo_state/quality_breaker/"
        "red_quality_artifact.json; resets -> operator_events.jsonl (event_id, "
        "artifact_sha256)",
    }


def _quality_measurement(quality_status: dict | None, *, quality_agreement: dict | None) -> dict:
    validation = None
    if quality_status:
        validation = (quality_status.get("claim_boundary") or {}).get("judge_validation")
    agreement = None
    if quality_agreement:
        agreement = {
            "judge_prompt_version": quality_agreement.get("judge_prompt_version"),
            "model_id": quality_agreement.get("model_id"),
            "clean_layer_per_dimension_kappa": (
                quality_agreement.get("clean_layer") or {}
            ).get("per_dimension_kappa"),
            "clean_layer_kappa_ci_95": (
                quality_agreement.get("clean_layer") or {}
            ).get("per_dimension_kappa_ci_95"),
            "claim_boundary": quality_agreement.get("claim_boundary"),
        }
    return {
        "note": "quoted verbatim from the evidence artifacts, never restated",
        "judge_validation": validation,
        "judge_agreement_quoted": agreement,
    }


def _autonomy(autonomy: dict | None) -> dict:
    if not autonomy:
        return {"available": False}
    return {
        "available": True,
        "claim_boundary": autonomy.get("claim_boundary"),
        "action_stats": autonomy.get("action_stats"),
        "tier_change_proposals": autonomy.get("tier_change_proposals"),
        "ledger": autonomy.get("ledger"),
        "policy": autonomy.get("policy"),
        "row_refs": "stats and proposals -> eval/autonomy_report.json (proposal_id); "
        "verdict window rows -> the ledger path+hash recorded above",
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["sections"]
    lines = [
        "# Oversight Evidence Pack",
        "",
        f"> {report['disclaimer']}",
        "",
        f"Claim boundary: `{json.dumps(report['claim_boundary'], sort_keys=True)}`",
        "",
        "## 1. Human oversight events",
        "",
    ]
    h = s["1_human_oversight_events"]
    for action, counts in h["verdict_counts_by_action"].items():
        tiers = h["tiers_observed_by_action"].get(action, [])
        lines.append(f"- `{action}` (tiers {tiers}): {json.dumps(counts, sort_keys=True)}")
    lines.append("")
    for e in h["verdict_events"]:
        lines.append(
            f"  - `{e['proposal_id']}` {e['verdict']} ({e['verdict_reason']}) "
            f"proposed {e['proposed_at']} decided {e['verdict_at']}"
        )
    lines += ["", "Committed outbound receipts (payload-hash bound):", ""]
    for r in h["committed_outbound_receipts"]:
        lines.append(
            f"  - receipt `{r['receipt_id']}` proposal `{r['proposal_id']}` "
            f"action {r['action']} sha256 `{r['payload_sha256']}` -> {r['target']}"
        )
    lines += ["", f"Row refs: {h['row_refs']}", ""]

    sod = s["2_separation_of_duties"]
    lines += ["## 2. Separation of duties", ""]
    lines.append(f"- Proposing role: {sod['design']['proposing_role']}")
    lines.append(
        f"- Proposer permissions: {', '.join(sod['design']['proposing_role_permissions'])}"
    )
    lines.append(f"- Enforcement: {sod['design']['enforcement']}")
    lines.append(f"- Runtime proof: {sod['runtime_proof']}")

    ab = s["3_authority_boundaries"]
    lines += ["", "## 3. Authority boundaries", ""]
    for spec in ab["action_taxonomy"]:
        lines.append(
            f"- `{spec['action']}` tier {spec['autonomy_tier']} "
            f"({spec['release_condition']}; customer_affecting={spec['customer_affecting']})"
        )
    lines.append(
        f"- Auto-executing rows ({ab['auto_executing']['condition']}): "
        f"{len(ab['auto_executing']['audit_trail_rows'])} audited "
        f"{ab['auto_executing']['audit_trail_rows']}"
    )

    sr = s["4_suppression_and_release"]
    lines += ["", "## 4. Suppression & release history", ""]
    lines.append(
        f"- Trigger suppressions: {len(sr['trigger_suppressions'])} "
        f"by reason {json.dumps(sr['suppression_reason_counts'], sort_keys=True)}"
    )
    for sup in sr["trigger_suppressions"]:
        lines.append(
            f"  - {sup['as_of']} `{sup['trigger_name']}` reason={sup['reason']} "
            f"ref `{sup['condition_instance']}`"
        )
    battery = sr["hold_release_rederivation_proof"]
    if battery:
        lines.append(
            f"- Hold/release re-derivation proof: `{battery['artifact']}` "
            f"score {battery['score']} hard_ok={battery['hard_ok']} "
            f"cases {[c['case_id'] for c in battery['cases']]}"
        )
    lines.append(f"- Row refs: {sr['row_refs']}")

    d = s["5_degradation_honesty"]
    lines += ["", "## 5. Degradation honesty", ""]
    lines.append(f"- Breaker artifact: `{json.dumps(d['quality_breaker_artifact'], sort_keys=True)}`")
    for e in d["operator_reset_events"]:
        lines.append(
            f"- Operator reset `{e.get('event_id')}` on artifact sha256 "
            f"`{e.get('artifact_sha256')}` at {e.get('recorded_at')}: {e.get('rationale')}"
        )

    q = s["6_quality_measurement"]
    lines += ["", "## 6. Quality measurement state", ""]
    lines.append(f"- {q['note']}")
    lines.append(f"- judge_validation: `{json.dumps(q['judge_validation'], sort_keys=True)}`")
    agreement = q["judge_agreement_quoted"]
    if agreement:
        lines.append(
            f"- judge_agreement ({agreement['judge_prompt_version']}, "
            f"{agreement['model_id']}): clean kappa "
            f"`{json.dumps(agreement['clean_layer_per_dimension_kappa'], sort_keys=True)}` "
            f"with 95% CIs in the JSON report"
        )

    a = s["7_autonomy_provenance"]
    lines += ["", "## 7. Autonomy provenance", ""]
    if a.get("available"):
        for stat in a["action_stats"] or []:
            lines.append(
                f"- `{stat.get('action_type')}` tier {stat.get('current_tier')}: "
                f"n={stat.get('n')} rates {json.dumps(stat.get('rates'), sort_keys=True)} "
                f"window {json.dumps(stat.get('window'), sort_keys=True)}"
            )
        for prop in a["tier_change_proposals"] or []:
            lines.append(
                f"- PROPOSAL `{prop.get('proposal_id')}`: {prop.get('proposal_type')} "
                f"{prop.get('action_type')} {prop.get('current_tier')}->"
                f"{prop.get('proposed_tier')} ({prop.get('effect')})"
            )
        lines.append(f"- Ledger: `{json.dumps(a.get('ledger'), sort_keys=True)}`")
    else:
        lines.append("- No autonomy report artifact loaded.")

    lines += ["", "## 8. Not instrumented", ""]
    for item in s["8_not_instrumented"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_oversight_report(
    *,
    root: Path = ROOT,
    json_out: Path = JSON_OUT,
    md_out: Path = MD_OUT,
) -> dict[str, Any]:
    report = build_oversight_report(root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(report), encoding="utf-8")
    return report


def _jsonl(root: Path, rel: str) -> list[dict]:
    path = root / rel
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _json(root: Path, rel: str) -> dict | None:
    path = root / rel
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, default=JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    args = parser.parse_args(argv)
    report = write_oversight_report(json_out=args.json_out, md_out=args.md_out)
    sections = report["sections"]
    print(
        json.dumps(
            {
                "json": str(args.json_out),
                "markdown": str(args.md_out),
                "verdict_events": len(sections["1_human_oversight_events"]["verdict_events"]),
                "suppressions": len(sections["4_suppression_and_release"]["trigger_suppressions"]),
                "not_instrumented": len(sections["8_not_instrumented"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
