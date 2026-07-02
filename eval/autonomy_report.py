"""Deterministic earned-autonomy report for G4.

The report consumes joined action_proposal/action_verdict-like JSONL rows and
emits proposal artifacts for owner review. It never edits the action taxonomy or
tier configuration; auto-apply is treated as a hard failure.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from ultra_csm.governance.csm_actions import CSM_ACTION_SPECS


REPO = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = REPO / "config" / "autonomy_policy.json"
DEFAULT_LEDGER_PATH = REPO / "eval" / "autonomy_verdict_ledger.jsonl"
DEFAULT_OUTPUT = REPO / "eval" / "autonomy_report.json"
VALID_VERDICTS = {"approve", "revise", "deny"}


class AutonomyPolicyError(ValueError):
    """The autonomy report was asked to do something unsafe or invalid."""


@dataclass(frozen=True)
class VerdictRecord:
    proposal_id: str
    action_type: str
    autonomy_tier: int
    verdict: str
    verdict_at: str
    verdict_reason: str


def build_autonomy_report(
    *,
    policy_path: Path = DEFAULT_POLICY_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    output_path: Path = DEFAULT_OUTPUT,
    auto_apply: bool = False,
) -> dict[str, Any]:
    policy = _load_json(policy_path)
    if auto_apply or bool(policy.get("auto_apply")):
        raise AutonomyPolicyError(
            "auto_apply is forbidden for earned-autonomy reports; "
            "the artifact may propose tier changes but must not mutate config"
        )

    records = _records_in_window(_load_ledger(ledger_path), _window(policy))
    grouped: dict[str, list[VerdictRecord]] = defaultdict(list)
    for record in records:
        grouped[record.action_type].append(record)

    stats = [
        _action_stats(action_type, grouped.get(action_type, ()), policy)
        for action_type in _action_order(grouped)
    ]
    proposals = [
        proposal
        for stat in stats
        for proposal in [_tier_change_proposal(stat, policy)]
        if proposal is not None
    ]
    hard_failures = _hard_failures(stats, proposals)
    artifact = {
        "artifact": "g4_earned_autonomy_report",
        "generated_by": "eval.autonomy_report",
        "claim_boundary": {
            "sim": True,
            "live": False,
            "promotion_artifacts_only": True,
            "mutates_tier_config": False,
        },
        "measurement_scope": (
            "Deterministic action-verdict ledger aggregation. No live tenant, "
            "no API calls, and no tier-config mutation."
        ),
        "policy": {
            "path": _display_path(policy_path),
            "hash": _hash_json(policy),
            "schema_version": policy.get("schema_version"),
            "window": _window(policy),
        },
        "ledger": {
            "path": _display_path(ledger_path),
            "hash": _hash_file(ledger_path),
            "records_in_window": len(records),
        },
        "score": {
            "passed": 0 if hard_failures else 1,
            "total": 1,
        },
        "hard_ok": not hard_failures,
        "hard_failures": hard_failures,
        "action_stats": stats,
        "tier_change_proposals": proposals,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AutonomyPolicyError(f"{path}: expected a JSON object")
    return payload


def _load_ledger(path: Path) -> tuple[VerdictRecord, ...]:
    records: list[VerdictRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise AutonomyPolicyError(f"{path}:{line_no}: expected a JSON object")
        records.append(_record_from_payload(payload, line_no=line_no))
    return tuple(records)


def _record_from_payload(payload: Mapping[str, Any], *, line_no: int) -> VerdictRecord:
    action_type = _required_str(payload, "action_type", fallback_key="action")
    if action_type not in CSM_ACTION_SPECS:
        raise AutonomyPolicyError(f"ledger line {line_no}: unknown action_type {action_type!r}")
    verdict = _required_str(payload, "verdict").lower()
    if verdict not in VALID_VERDICTS:
        raise AutonomyPolicyError(f"ledger line {line_no}: unknown verdict {verdict!r}")
    tier = int(payload.get("autonomy_tier", CSM_ACTION_SPECS[action_type].autonomy_tier))
    reason = (
        payload.get("verdict_reason")
        or payload.get("rejection_reason")
        or payload.get("rationale")
        or "unspecified"
    )
    return VerdictRecord(
        proposal_id=_required_str(payload, "proposal_id"),
        action_type=action_type,
        autonomy_tier=tier,
        verdict=verdict,
        verdict_at=_required_str(payload, "verdict_at", fallback_key="created_at"),
        verdict_reason=str(reason),
    )


def _required_str(payload: Mapping[str, Any], key: str, *, fallback_key: str | None = None) -> str:
    value = payload.get(key)
    if value is None and fallback_key is not None:
        value = payload.get(fallback_key)
    if not isinstance(value, str) or not value:
        raise AutonomyPolicyError(f"ledger field {key} is required")
    return value


def _window(policy: Mapping[str, Any]) -> dict[str, str]:
    raw = policy.get("window")
    if not isinstance(raw, dict):
        raise AutonomyPolicyError("policy.window must be an object")
    start = raw.get("start")
    end = raw.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        raise AutonomyPolicyError("policy.window.start and policy.window.end are required")
    return {"start": start, "end": end}


def _records_in_window(
    records: tuple[VerdictRecord, ...],
    window: Mapping[str, str],
) -> tuple[VerdictRecord, ...]:
    start = window["start"]
    end = window["end"]
    return tuple(
        record
        for record in records
        if start <= record.verdict_at[:10] <= end
    )


def _action_order(grouped: Mapping[str, list[VerdictRecord]]) -> tuple[str, ...]:
    known = tuple(CSM_ACTION_SPECS)
    extras = tuple(sorted(action for action in grouped if action not in CSM_ACTION_SPECS))
    return known + extras


def _action_stats(
    action_type: str,
    records: list[VerdictRecord] | tuple[VerdictRecord, ...],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    spec = CSM_ACTION_SPECS[action_type]
    counts = Counter(record.verdict for record in records)
    deny_reasons = Counter(
        record.verdict_reason for record in records if record.verdict == "deny"
    )
    revise_reasons = Counter(
        record.verdict_reason for record in records if record.verdict == "revise"
    )
    high_risk_reasons = set(_str_list(policy.get("high_risk_rejection_reasons", ())))
    high_risk_denies = sum(
        count for reason, count in deny_reasons.items() if reason in high_risk_reasons
    )
    timestamps = sorted(record.verdict_at for record in records)
    n = len(records)
    tier_values = sorted({record.autonomy_tier for record in records}) or [spec.autonomy_tier]
    return {
        "action_type": action_type,
        "current_tier": spec.autonomy_tier,
        "observed_tiers": tier_values,
        "release_condition": spec.release_condition,
        "customer_affecting": spec.customer_affecting,
        "window": {
            "first_verdict_at": timestamps[0] if timestamps else None,
            "last_verdict_at": timestamps[-1] if timestamps else None,
        },
        "n": n,
        "counts": {
            "approve": counts.get("approve", 0),
            "revise": counts.get("revise", 0),
            "deny": counts.get("deny", 0),
        },
        "rates": {
            "approve": _rate(counts.get("approve", 0), n),
            "revise": _rate(counts.get("revise", 0), n),
            "deny": _rate(counts.get("deny", 0), n),
        },
        "rejection_reasons": dict(sorted(deny_reasons.items())),
        "revision_reasons": dict(sorted(revise_reasons.items())),
        "high_risk_denials": high_risk_denies,
    }


def _tier_change_proposal(
    stat: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any] | None:
    current_tier = int(stat["current_tier"])
    bounds = policy.get("tier_bounds", {})
    if not isinstance(bounds, dict):
        raise AutonomyPolicyError("policy.tier_bounds must be an object")
    min_tier = int(bounds.get("min", 1))
    max_tier = int(bounds.get("max", 3))
    promotion = _thresholds(policy, "promotion")
    demotion = _thresholds(policy, "demotion")
    n = int(stat["n"])
    rates = stat["rates"]

    if (
        n >= int(promotion["min_n"])
        and current_tier > min_tier
        and float(rates["approve"]) >= float(promotion["min_approve_rate"])
        and float(rates["revise"]) <= float(promotion["max_revise_rate"])
        and float(rates["deny"]) <= float(promotion["max_deny_rate"])
        and int(stat["high_risk_denials"]) == 0
    ):
        proposed_tier = max(min_tier, current_tier - int(promotion["tier_step"]))
        return _proposal("promotion", stat, current_tier, proposed_tier, "approval_rate_threshold")

    demotion_triggered = (
        n >= int(demotion["min_n"])
        and (
            float(rates["deny"]) >= float(demotion["min_deny_rate"])
            or float(rates["revise"]) >= float(demotion["min_revise_rate"])
            or (
                int(stat["high_risk_denials"]) > 0
                and float(rates["deny"]) >= float(demotion["min_high_risk_deny_rate"])
            )
        )
    )
    if demotion_triggered and current_tier < max_tier:
        proposed_tier = min(max_tier, current_tier + int(demotion["tier_step"]))
        return _proposal("demotion", stat, current_tier, proposed_tier, "verdict_friction_threshold")
    return None


def _thresholds(policy: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    raw = policy.get(key)
    if not isinstance(raw, dict):
        raise AutonomyPolicyError(f"policy.{key} must be an object")
    return raw


def _proposal(
    proposal_type: str,
    stat: Mapping[str, Any],
    current_tier: int,
    proposed_tier: int,
    trigger: str,
) -> dict[str, Any]:
    payload = {
        "proposal_type": proposal_type,
        "action_type": stat["action_type"],
        "current_tier": current_tier,
        "proposed_tier": proposed_tier,
        "n": stat["n"],
        "rates": stat["rates"],
        "trigger": trigger,
    }
    return {
        "proposal_id": "g4-tier-change-" + _hash_json(payload).split(":", 1)[1][:16],
        **payload,
        "artifact_only": True,
        "requires_owner_review": True,
        "effect": "proposal_only_no_config_mutation",
    }


def _hard_failures(
    stats: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> list[str]:
    failures = []
    if not stats:
        failures.append("no_action_stats")
    if any(not proposal.get("artifact_only") for proposal in proposals):
        failures.append("tier_change_proposal_not_artifact_only")
    return failures


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _str_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _hash_json(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--auto-apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        artifact = build_autonomy_report(
            policy_path=args.policy,
            ledger_path=args.ledger,
            output_path=args.output,
            auto_apply=args.auto_apply,
        )
    except AutonomyPolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "artifact": _display_path(args.output),
        "hard_ok": artifact["hard_ok"],
        "records_in_window": artifact["ledger"]["records_in_window"],
        "tier_change_proposals": len(artifact["tier_change_proposals"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
