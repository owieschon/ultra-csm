"""MP-B deterministic internal-bridge battery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.narrative_shared import cases_as_of
from ultra_csm.internal_bridge import (
    InternalBridgePacketRequest,
    build_internal_bridge_packet,
    route_internal_bridge,
)

GOLD_PATH = Path(__file__).parent / "gold" / "fleetops_handoff_expected_actions.json"
ARTIFACT_PATH = Path(__file__).with_name("internal_bridge_battery.json")


def run_battery() -> dict[str, Any]:
    rows = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    failed_cases: list[str] = []

    for row in rows:
        result = _check_row(row)
        cases.append(result)
        if not result["ok"]:
            failed_cases.append(result["case"])

    return {
        "name": "internal_bridge_battery",
        "gold_path": str(GOLD_PATH),
        "hard_ok": not failed_cases,
        "failed_cases": failed_cases,
        "cases": cases,
    }


def _check_row(row: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    account_slug = row["account_slug"]
    checkpoint_day = row["checkpoint_day"]
    review_id = row.get("handoff", {}).get("review_id", f"{account_slug}@{checkpoint_day}")
    account_id = account_id_for(account_slug)
    as_of = f"checkpoint-day-{checkpoint_day}"
    decision = route_internal_bridge(tuple(cases_as_of(account_id, checkpoint_day)), as_of=as_of)
    packet = build_internal_bridge_packet(
        InternalBridgePacketRequest(
            tenant_id=row["tenant"],
            account_id=account_id,
            account_name=account_slug,
            as_of=as_of,
            decision=decision,
        )
    )

    required = row["required"]
    expected_targets = tuple(row.get("handoff", {}).get("target_in", ()))
    forbidden_targets = set(row.get("handoff", {}).get("forbidden_targets", ()))
    forbidden_motions = set(row.get("forbidden_motions", ()))
    evidence_ids = {ref.source_id for ref in decision.evidence}
    required_evidence = set(required.get("evidence_must_include", ()))

    if row["mode"] == "none":
        if not decision.abstained:
            problems.append(f"expected abstained=true, got target={decision.target}")
        if packet.abstained is not True:
            problems.append("expected packet abstained=true")
        if decision.motion is not None:
            problems.append(f"expected no motion, got {decision.motion}")
    else:
        if decision.abstained:
            problems.append("expected routed decision, got abstained=true")
        if packet.abstained is not False:
            problems.append("expected packet abstained=false")
        if decision.motion not in required.get("motion_in", ()):
            problems.append(
                f"motion {decision.motion!r} not in required.motion_in={required.get('motion_in')!r}"
            )
        if expected_targets and decision.target not in expected_targets:
            problems.append(f"target {decision.target!r} not in target_in={expected_targets!r}")
        if decision.signal != required.get("signal"):
            problems.append(f"signal {decision.signal!r} != required.signal={required.get('signal')!r}")
        missing = sorted(required_evidence - evidence_ids)
        if missing:
            problems.append(f"missing required evidence ids: {missing}")
        packet_missing = sorted(required_evidence - set(packet.cited_evidence_ids))
        if packet_missing:
            problems.append(f"packet missing required evidence ids: {packet_missing}")

    if decision.motion in forbidden_motions:
        problems.append(f"forbidden motion emitted: {decision.motion}")
    packet_body = packet.body.lower()
    for forbidden_motion in forbidden_motions:
        if forbidden_motion.lower() in packet_body:
            problems.append(f"packet body contains forbidden motion: {forbidden_motion}")
    if decision.target in forbidden_targets:
        problems.append(f"forbidden target emitted: {decision.target}")

    return {
        "case": review_id,
        "ok": not problems,
        "problems": problems,
        "detail": {
            "account_slug": account_slug,
            "checkpoint_day": checkpoint_day,
            "mode": row["mode"],
            "expected_motion_in": required.get("motion_in", ()),
            "expected_target_in": expected_targets,
            "decision": {
                "target": decision.target,
                "motion": decision.motion,
                "signal": decision.signal,
                "abstained": decision.abstained,
                "evidence_ids": sorted(evidence_ids),
            },
            "packet": {
                "target": packet.target,
                "motion": packet.motion,
                "abstained": packet.abstained,
                "cited_evidence_ids": list(packet.cited_evidence_ids),
                "body": packet.body,
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    report = run_battery()
    if args.check:
        if not report["hard_ok"]:
            raise SystemExit(json.dumps(report, indent=2))
    else:
        ARTIFACT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
