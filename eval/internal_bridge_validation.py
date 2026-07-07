"""MP-B Phase B3 internal-bridge validation report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Protocol

from eval.internal_bridge_battery import GOLD_PATH, run_battery
from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_csm import KAPPA_GATE, QUALITY_DIMENSIONS, PASSING_SCORE
from eval.judge_validation import judge_validation_status
from ultra_csm.data_plane.fixtures import account_id_for
from ultra_csm.data_plane.narrative_shared import cases_as_of
from ultra_csm.internal_bridge import (
    InternalBridgePacket,
    InternalBridgePacketRequest,
    build_internal_bridge_packet,
    route_internal_bridge,
)

ARTIFACT_PATH = Path(__file__).with_name("internal_bridge_validation_report.json")


class PacketProseScorer(Protocol):
    model_id: str
    prompt_version: str
    reasoning: bool

    def score_packet(
        self,
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> tuple[dict[str, int], dict[str, str]]:
        ...


class LivePacketProseScorer:
    """Adapter around the shipped Slot B quality judge."""

    prompt_version = JUDGE_PROMPT_VERSION
    reasoning = True

    def __init__(self, judge: AnthropicQualityJudge | None = None) -> None:
        self._judge = judge or AnthropicQualityJudge(reasoning=True)
        self._judge._max_tokens = max(self._judge._max_tokens, 1200)
        self._terse_judge = AnthropicQualityJudge(model_id=self._judge.model_id, reasoning=False)
        self.model_id = self._judge.model_id

    def score_packet(
        self,
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> tuple[dict[str, int], dict[str, str]]:
        last_error: Exception | None = None
        for _attempt in range(3):
            try:
                return self._judge.score_output_with_reasons(request, output)
            except (ValueError, JSONDecodeError) as exc:
                last_error = exc
        scores = self._terse_judge.score_output(request, output)
        reason = f"terse fallback after {type(last_error).__name__}"
        return scores, {dimension: reason for dimension in QUALITY_DIMENSIONS}


class FixturePacketProseScorer:
    """Deterministic local scorer for tests and dry-run structure checks."""

    model_id = "fixture-internal-bridge-prose-scorer"
    prompt_version = JUDGE_PROMPT_VERSION
    reasoning = False

    def score_packet(
        self,
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> tuple[dict[str, int], dict[str, str]]:
        del request, output
        scores = {dimension: 3 for dimension in QUALITY_DIMENSIONS}
        reasons = {dimension: "fixture structural pass" for dimension in QUALITY_DIMENSIONS}
        return scores, reasons


def build_validation_report(*, prose_scorer: PacketProseScorer) -> dict[str, Any]:
    rows = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    battery = run_battery()
    case_rows: list[dict[str, Any]] = []
    matrix: dict[str, dict[str, int]] = {}
    confidently_wrong: list[dict[str, str]] = []

    for row in rows:
        case = _build_case(row, prose_scorer)
        case_rows.append(case)
        oracle_cell = case["confusion"]["oracle_target_cell"]
        agent_cell = case["confusion"]["agent_target_cell"]
        matrix.setdefault(oracle_cell, {})
        matrix[oracle_cell][agent_cell] = matrix[oracle_cell].get(agent_cell, 0) + 1
        if case["confusion"]["confidently_wrong"]:
            confidently_wrong.append(
                {
                    "case": case["case"],
                    "oracle_target_cell": oracle_cell,
                    "agent_target_cell": agent_cell,
                }
            )

    prose_failures = [
        case["case"]
        for case in case_rows
        if case["packet_prose"]["aggregate_pass"] is False
    ]
    judge_status = judge_validation_status()
    hard_ok = bool(battery["hard_ok"]) and not confidently_wrong
    verdict = (
        "existence_proof_holds_pending_owner_validated_verdict"
        if hard_ok
        else "partial_or_failed_measurement"
    )
    return {
        "artifact": "internal_bridge_validation_report",
        "schema_version": 1,
        "generated_by": "eval.internal_bridge_validation",
        "gold_path": str(GOLD_PATH),
        "battery_artifact": "eval/internal_bridge_battery.py::run_battery",
        "routing_core_hard_ok": battery["hard_ok"],
        "routing_failed_cases": battery["failed_cases"],
        "verdict": verdict,
        "claim_boundary": (
            "Mechanical spike validation only. The owner-confirmed validated verdict, "
            "independent inter-rater ceiling, and VM-8 outcome durability remain outside this artifact."
        ),
        "confusion_matrix": {
            "rows": "oracle target cell",
            "columns": "agent target cell",
            "cells": matrix,
            "confidently_wrong_cells": confidently_wrong,
        },
        "abstain_axis": {
            "oracle_abstain_agent_abstain": sum(
                1
                for case in case_rows
                if case["confusion"]["oracle_abstain"] and case["confusion"]["agent_abstain"]
            ),
            "oracle_route_agent_abstain": sum(
                1
                for case in case_rows
                if not case["confusion"]["oracle_abstain"] and case["confusion"]["agent_abstain"]
            ),
            "oracle_abstain_agent_route": sum(
                1
                for case in case_rows
                if case["confusion"]["oracle_abstain"] and not case["confusion"]["agent_abstain"]
            ),
            "oracle_route_agent_route": sum(
                1
                for case in case_rows
                if not case["confusion"]["oracle_abstain"] and not case["confusion"]["agent_abstain"]
            ),
        },
        "packet_prose_judge": {
            "dimensions": list(QUALITY_DIMENSIONS),
            "passing_score": PASSING_SCORE,
            "kappa_gate": KAPPA_GATE,
            "judge_model_id": prose_scorer.model_id,
            "judge_prompt_version": prose_scorer.prompt_version,
            "judge_reasoning": prose_scorer.reasoning,
            "judge_validation_status": judge_status,
            "packet_failures": prose_failures,
            "note": "The existing Slot B judge is reused; no new judge is validated here.",
        },
        "inter_rater": {
            "status": "not_computed",
            "single_oracle": True,
            "reason": (
                "No independent second human labeler was supplied. The same-model "
                "ambiguity probe is disclosed as correlated and is not inter-rater reliability."
            ),
        },
        "cases": case_rows,
    }


def _build_case(row: dict[str, Any], prose_scorer: PacketProseScorer) -> dict[str, Any]:
    account_slug = row["account_slug"]
    checkpoint_day = row["checkpoint_day"]
    review_id = row.get("handoff", {}).get("review_id", f"{account_slug}@{checkpoint_day}")
    account_id = account_id_for(account_slug)
    as_of = f"checkpoint-day-{checkpoint_day}"
    decision = route_internal_bridge(tuple(cases_as_of(account_id, checkpoint_day)), as_of=as_of)
    packet_request = InternalBridgePacketRequest(
        tenant_id=row["tenant"],
        account_id=account_id,
        account_name=account_slug,
        as_of=as_of,
        decision=decision,
    )
    packet = build_internal_bridge_packet(packet_request)
    quality_request, quality_output = packet_quality_payload(packet_request, packet)
    scores, reasons = prose_scorer.score_packet(quality_request, quality_output)

    target_in = tuple(row.get("handoff", {}).get("target_in", ()))
    oracle_target_cell = _oracle_target_cell(row)
    agent_target_cell = "abstain" if decision.abstained else str(decision.target)
    confident_route_to_wrong_target = (
        not decision.abstained
        and (
            row["mode"] == "none"
            or (target_in and decision.target not in target_in)
        )
    )
    return {
        "case": review_id,
        "account_slug": account_slug,
        "checkpoint_day": checkpoint_day,
        "confusion": {
            "oracle_target_cell": oracle_target_cell,
            "agent_target_cell": agent_target_cell,
            "oracle_abstain": row["mode"] == "none",
            "agent_abstain": decision.abstained,
            "confidently_wrong": confident_route_to_wrong_target,
        },
        "oracle": {
            "mode": row["mode"],
            "target_in": list(target_in),
            "motion_in": list(row["required"].get("motion_in", ())),
            "signal": row["required"].get("signal"),
            "evidence_must_include": list(row["required"].get("evidence_must_include", ())),
        },
        "agent": {
            "target": decision.target,
            "motion": decision.motion,
            "signal": decision.signal,
            "abstained": decision.abstained,
            "evidence_ids": [ref.source_id for ref in decision.evidence],
        },
        "packet": {
            "target": packet.target,
            "motion": packet.motion,
            "abstained": packet.abstained,
            "reason": packet.reason,
            "body": packet.body,
            "cited_evidence_ids": list(packet.cited_evidence_ids),
            "model_id": packet.model_id,
            "prompt_version": packet.prompt_version,
        },
        "packet_prose": {
            "scores": scores,
            "reasons": reasons,
            "aggregate_pass": all(scores[dimension] >= PASSING_SCORE for dimension in QUALITY_DIMENSIONS),
        },
    }


def packet_quality_payload(
    request: InternalBridgePacketRequest,
    packet: InternalBridgePacket,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision = request.decision
    evidence = [
        {
            "source": ref.source,
            "source_id": ref.source_id,
            "field": ref.field,
            "observed_at": ref.observed_at,
        }
        for ref in decision.evidence
    ]
    factor_name = decision.signal or "internal_bridge_abstain"
    quality_request = {
        "tenant_id": request.tenant_id,
        "account_id": request.account_id,
        "account_name": request.account_name,
        "disposition": "internal_review",
        "recommended_action": "internal_bridge_packet",
        "customer_contact_allowed": False,
        "priority": {
            "score": None,
            "factors": [{"name": factor_name, "value": 1.0, "contribution": 0}],
        },
        "evidence": evidence,
        "as_of": request.as_of,
        "contact_name": None,
        "contact_email": None,
        "untrusted_text_fragments": (),
        "internal_bridge_decision": asdict(decision),
    }
    quality_output = {
        "reason": packet.body,
        "customer_draft": None,
        "cited_evidence_ids": list(packet.cited_evidence_ids),
        "abstained": packet.abstained,
        "target": packet.target,
        "motion": packet.motion,
    }
    return quality_request, quality_output


def _oracle_target_cell(row: dict[str, Any]) -> str:
    if row["mode"] == "none":
        return "abstain"
    target_in = tuple(row.get("handoff", {}).get("target_in", ()))
    return "|".join(target_in) if target_in else "route_unspecified"


def write_validation_report(
    *,
    output_path: Path = ARTIFACT_PATH,
    prose_scorer: PacketProseScorer,
) -> dict[str, Any]:
    report = build_validation_report(prose_scorer=prose_scorer)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    parser.add_argument(
        "--prose",
        choices=("live", "fixture"),
        default="live",
        help="Use the shipped Anthropic judge or a deterministic fixture scorer.",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    scorer: PacketProseScorer
    if args.prose == "fixture":
        scorer = FixturePacketProseScorer()
    else:
        scorer = LivePacketProseScorer()
    report = write_validation_report(output_path=args.output, prose_scorer=scorer)
    if args.check and report["confusion_matrix"]["confidently_wrong_cells"]:
        raise SystemExit(json.dumps(report["confusion_matrix"], indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
