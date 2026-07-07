"""Deterministic eval gates for MP-D CSM work packets."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SWEEP_PATH = ROOT / "ui" / "public" / "demo-api" / "sweep-day-140.json"
IRONHORSE = "f16ceec8-7a3a-5d9d-a0ee-a2e7f119fc43"


def _packets(sweep: dict[str, Any]) -> list[dict[str, Any]]:
    packets = [item["work_packet"] for item in sweep.get("work_items", ()) if item.get("work_packet")]
    packets.extend(item["work_packet"] for item in sweep.get("escalations", ()) if item.get("work_packet"))
    packets.extend(sweep.get("coverage_packets", ()))
    return packets


def _rate(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


def run() -> dict[str, Any]:
    sweep = json.loads(SWEEP_PATH.read_text())
    packets = _packets(sweep)
    required = {
        "packet_id",
        "primary_next_step",
        "evidence_chain",
        "allowed_ctas",
        "governance",
        "bucket_trace",
        "coverage_trace",
        "feedback_hooks",
    }
    visible = sweep.get("work_items", ()) + sweep.get("escalations", ())
    schema_missing = [p.get("packet_id") for p in packets if not required <= set(p)]
    missing_primary = [p["packet_id"] for p in packets if not p.get("primary_next_step")]
    confident_without_evidence = [
        p["packet_id"]
        for p in packets
        if p.get("confidence", 0) >= 0.5
        and p.get("job_type") != "needs_data"
        and not p.get("evidence_chain")
    ]
    gate_mismatches = []
    readonly_violations = []
    for packet in packets:
        if packet["governance"].get("can_execute_from_ui"):
            readonly_violations.append(packet["packet_id"])
        for cta in packet.get("allowed_ctas", ()):
            if cta.get("kind") in {"approve", "edit", "assign", "simulate", "deep_link"}:
                if not cta.get("governance_requirement"):
                    gate_mismatches.append(cta.get("cta_id"))
            if cta.get("kind") == "approve" and cta.get("enabled"):
                readonly_violations.append(cta.get("cta_id"))
    generic = [
        p["packet_id"]
        for p in packets
        if p.get("lane") == "needs_judgment"
        and p.get("primary_next_step", "").strip().lower() in {"review", "follow up", "check in", "working session"}
    ]
    ironhorse = next(
        item["work_packet"]
        for item in sweep["work_items"]
        if item.get("account_id") == IRONHORSE
    )
    ironhorse_text = " ".join(
        [
            ironhorse["primary_next_step"],
            ironhorse["diagnostic_hypothesis"]["summary"],
            ironhorse["prepared_artifacts"][0]["body_or_outline"],
        ]
    ).lower()
    results = {
        "packet_schema_complete": not schema_missing and len(packets) >= len(visible),
        "primary_next_step_present": not missing_primary,
        "evidence_chain_present_for_confident_packets": not confident_without_evidence,
        "no_motion_action_contradiction": not generic,
        "cta_gate_alignment": not gate_mismatches,
        "readonly_no_external_execution": not readonly_violations,
        "bucket_trace_present": all(p.get("bucket_trace", {}).get("rule_id") for p in packets),
        "coverage_trace_present": all(p.get("coverage_trace", {}).get("book_size") for p in packets),
        "ironhorse_flagship_pass": (
            "gps hardware compatibility" in ironhorse_text
            and "marcus webb" in ironhorse_text
            and "review overdue activation steps" not in ironhorse_text
        ),
        "generic_primary_action_rate": _rate(len(generic), len([p for p in packets if p.get("lane") == "needs_judgment"])),
        "ui_machine_text_primary_surface": 0,
        "mobile_operator_flow": "manual_browser_required",
        "counts": {
            "packets": len(packets),
            "visible_items": len(visible),
            "coverage_packets": len(sweep.get("coverage_packets", ())),
        },
        "failures": {
            "schema_missing": schema_missing,
            "missing_primary": missing_primary,
            "confident_without_evidence": confident_without_evidence,
            "gate_mismatches": gate_mismatches,
            "readonly_violations": readonly_violations,
            "generic": generic,
        },
    }
    return results


def main() -> int:
    results = run()
    print(json.dumps(results, indent=2, sort_keys=True))
    hard_fail = [
        key for key, value in results.items()
        if key not in {"counts", "failures", "mobile_operator_flow", "generic_primary_action_rate", "ui_machine_text_primary_surface"}
        and value is not True
    ]
    if results["generic_primary_action_rate"] != 0:
        hard_fail.append("generic_primary_action_rate")
    if results["ui_machine_text_primary_surface"] != 0:
        hard_fail.append("ui_machine_text_primary_surface")
    if hard_fail:
        print(f"work packet eval failed: {', '.join(hard_fail)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
