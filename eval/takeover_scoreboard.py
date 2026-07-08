"""Read-only takeover scoreboard for CSM agent work.

The scoreboard mirrors existing ledger/verdict/rejection surfaces. It does not
grade packets, run workflows, or release actions. Every metric carries an
instrumentation status so absent sources stay visible rather than becoming fake
zeroes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

import psycopg

from ultra_csm.audit_ledger import AuditEvent, list_audit_events
from ultra_csm.platform.db import session
from ultra_csm.rejection_ledger import RejectionLedger


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "takeover_scoreboard.json"
DEFAULT_VERDICT_FIXTURE = REPO / "eval" / "autonomy_verdict_ledger.jsonl"
DEFAULT_REVIEW_MINUTES_PER_VERDICT = 2.5
MetricStatus = Literal["measured", "modeled", "not_instrumented"]


@dataclass(frozen=True)
class GateVerdictRecord:
    proposal_id: str
    category: str
    action_type: str
    autonomy_tier: int
    verdict: str
    verdict_reason: str | None = None


@dataclass(frozen=True)
class MetricValue:
    name: str
    value: Any
    status: MetricStatus
    source: str
    dependency: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ScoreboardRow:
    category: str
    account_count: int
    metrics: tuple[MetricValue, ...]


@dataclass(frozen=True)
class TakeoverScoreboard:
    artifact: str
    generated_by: str
    metric_status_values: tuple[MetricStatus, ...]
    review_minutes_per_verdict: float
    source_summary: dict[str, Any]
    book_rollup: ScoreboardRow
    rows: tuple[ScoreboardRow, ...]
    instrumentation_gaps: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_takeover_scoreboard(
    *,
    verdict_records: Iterable[GateVerdictRecord],
    audit_events: Iterable[AuditEvent] = (),
    rejection_ledger: RejectionLedger | None = None,
    accounts_in_scope: int | None = None,
    review_minutes_per_verdict: float = DEFAULT_REVIEW_MINUTES_PER_VERDICT,
) -> TakeoverScoreboard:
    verdicts = tuple(verdict_records)
    events = tuple(audit_events)
    rejections = rejection_ledger.all_records() if rejection_ledger is not None else ()
    categories = sorted({record.category for record in verdicts} | {"book"})
    rows = tuple(
        _row_for_category(
            category,
            verdicts=tuple(record for record in verdicts if record.category == category),
            audit_events=events,
            rejection_reasons=tuple(record.reason for record in rejections),
            accounts_in_scope=accounts_in_scope,
            review_minutes_per_verdict=review_minutes_per_verdict,
        )
        for category in categories
        if category != "book"
    )
    rollup = _row_for_category(
        "book",
        verdicts=verdicts,
        audit_events=events,
        rejection_reasons=tuple(record.reason for record in rejections),
        accounts_in_scope=accounts_in_scope,
        review_minutes_per_verdict=review_minutes_per_verdict,
    )
    gaps = tuple(
        dict.fromkeys(
            gap
            for row in (rollup, *rows)
            for metric in row.metrics
            if metric.status == "not_instrumented"
            for gap in (metric.dependency or metric.name,)
        )
    )
    return TakeoverScoreboard(
        artifact="takeover_scoreboard",
        generated_by="eval.takeover_scoreboard",
        metric_status_values=("measured", "modeled", "not_instrumented"),
        review_minutes_per_verdict=review_minutes_per_verdict,
        source_summary={
            "verdict_records": len(verdicts),
            "audit_events": len(events),
            "rejection_records": len(rejections),
            "accounts_in_scope": accounts_in_scope,
        },
        book_rollup=rollup,
        rows=rows,
        instrumentation_gaps=gaps,
    )


def read_gate_verdict_records(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    now: Any = None,
) -> tuple[GateVerdictRecord, ...]:
    """Read proposal/verdict rows from the existing governance tables."""

    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT p.proposal_id::text, p.intent, p.action, p.autonomy_tier, "
            "       v.verdict, v.rationale "
            "FROM action_proposal p "
            "JOIN action_verdict v ON v.proposal_id = p.proposal_id "
            "ORDER BY p.action, p.proposal_id"
        )
        rows = cur.fetchall()
    return tuple(
        GateVerdictRecord(
            proposal_id=str(row[0]),
            category=_category_for(action_type=str(row[2]), intent=str(row[1] or "")),
            action_type=str(row[2]),
            autonomy_tier=int(row[3]),
            verdict=str(row[4]),
            verdict_reason=str(row[5]) if row[5] is not None else None,
        )
        for row in rows
    )


def read_audit_events(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    limit: int = 500,
    now: Any = None,
) -> tuple[AuditEvent, ...]:
    return list_audit_events(
        conn,
        tenant_id=tenant_id,
        actor_id=actor_id,
        limit=limit,
        now=now,
    )


def read_verdict_fixture(path: Path = DEFAULT_VERDICT_FIXTURE) -> tuple[GateVerdictRecord, ...]:
    records: list[GateVerdictRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        action_type = str(raw["action_type"])
        records.append(
            GateVerdictRecord(
                proposal_id=str(raw["proposal_id"]),
                category=_category_for(action_type=action_type, intent="fixture"),
                action_type=action_type,
                autonomy_tier=int(raw["autonomy_tier"]),
                verdict=str(raw["verdict"]),
                verdict_reason=raw.get("verdict_reason"),
            )
        )
    return tuple(records)


def write_scoreboard(
    scoreboard: TakeoverScoreboard,
    *,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    payload = json.loads(json.dumps(scoreboard.to_dict(), sort_keys=True))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def build_fixture_scoreboard(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    verdict_fixture: Path = DEFAULT_VERDICT_FIXTURE,
) -> dict[str, Any]:
    scoreboard = build_takeover_scoreboard(
        verdict_records=read_verdict_fixture(verdict_fixture),
        accounts_in_scope=9,
    )
    return write_scoreboard(scoreboard, output_path=output_path)


def _row_for_category(
    category: str,
    *,
    verdicts: tuple[GateVerdictRecord, ...],
    audit_events: tuple[AuditEvent, ...],
    rejection_reasons: tuple[str, ...],
    accounts_in_scope: int | None,
    review_minutes_per_verdict: float,
) -> ScoreboardRow:
    account_count = accounts_in_scope or 0
    metrics = (
        _coverage_metric(category, audit_events, accounts_in_scope),
        _release_mix_metric(verdicts),
        _verdict_mix_metric(verdicts),
        _human_minutes_metric(verdicts, accounts_in_scope, review_minutes_per_verdict),
        _sampled_miss_rate_metric(),
        _denial_taxonomy_metric(verdicts, rejection_reasons),
        _outcome_reconciliation_metric(),
        _abstention_rate_metric(audit_events),
    )
    return ScoreboardRow(category=category, account_count=account_count, metrics=metrics)


def _coverage_metric(
    category: str,
    audit_events: tuple[AuditEvent, ...],
    accounts_in_scope: int | None,
) -> MetricValue:
    packet_events = tuple(
        event for event in audit_events
        if event.event_type.endswith(".packet") or event.event_type == "slot_b.draft"
    )
    if not packet_events or not accounts_in_scope:
        return MetricValue(
            "coverage",
            None,
            "not_instrumented",
            "audit_ledger",
            dependency="MP-D2 packet/workflow packet events",
            notes="Packet or account-scope rows are not available for this category.",
        )
    scoped = packet_events if category == "book" else tuple(
        event for event in packet_events if _event_category(event) == category
    )
    return MetricValue(
        "coverage",
        round(len(scoped) / accounts_in_scope, 4),
        "measured",
        "audit_ledger",
    )


def _release_mix_metric(verdicts: tuple[GateVerdictRecord, ...]) -> MetricValue:
    if not verdicts:
        return _not_instrumented("release_mix", "action_proposal/action_verdict")
    counts = Counter(_release_bucket(record) for record in verdicts)
    return MetricValue(
        "release_mix",
        _share_dict(counts),
        "measured",
        "action_proposal.autonomy_tier",
        dependency="MP-E graduation state for auto-vs-batch split",
        notes="Tier-derived release posture is measured; graduation split is not yet instrumented.",
    )


def _verdict_mix_metric(verdicts: tuple[GateVerdictRecord, ...]) -> MetricValue:
    if not verdicts:
        return _not_instrumented("verdict_mix", "action_verdict")
    return MetricValue(
        "verdict_mix",
        _share_dict(Counter(record.verdict for record in verdicts)),
        "measured",
        "action_verdict.verdict",
    )


def _human_minutes_metric(
    verdicts: tuple[GateVerdictRecord, ...],
    accounts_in_scope: int | None,
    review_minutes_per_verdict: float,
) -> MetricValue:
    if not verdicts or not accounts_in_scope:
        value = None
    else:
        value = round((len(verdicts) * review_minutes_per_verdict) / accounts_in_scope, 2)
    return MetricValue(
        "human_minutes_per_account_week",
        value,
        "modeled",
        "action_verdict count * configured review_minutes_per_verdict",
        dependency="review dwell-time instrumentation",
        notes=(
            f"Modeled with {review_minutes_per_verdict:g} minutes per verdict until "
            "real review dwell time is instrumented."
        ),
    )


def _sampled_miss_rate_metric() -> MetricValue:
    return MetricValue(
        "sampled_miss_rate",
        None,
        "not_instrumented",
        "MP-E sampling audit",
        dependency="MP-E graduation sampling audit records",
    )


def _denial_taxonomy_metric(
    verdicts: tuple[GateVerdictRecord, ...],
    rejection_reasons: tuple[str, ...],
) -> MetricValue:
    reasons = [
        reason for reason in rejection_reasons
        if reason
    ]
    reasons.extend(
        record.verdict_reason or "deny_without_reason"
        for record in verdicts
        if record.verdict == "deny"
    )
    if not reasons:
        return _not_instrumented("denial_taxonomy", "RejectionLedger.reason/action_verdict.rationale")
    return MetricValue(
        "denial_taxonomy",
        dict(Counter(reasons).most_common(8)),
        "measured",
        "RejectionLedger.reason/action_verdict.rationale",
    )


def _outcome_reconciliation_metric() -> MetricValue:
    return MetricValue(
        "outcome_reconciliation_coverage",
        None,
        "not_instrumented",
        "VM-8 outcome states",
        dependency="VM-8-full outcome observation",
    )


def _abstention_rate_metric(audit_events: tuple[AuditEvent, ...]) -> MetricValue:
    if not audit_events:
        return MetricValue(
            "abstention_rate",
            None,
            "not_instrumented",
            "workflow envelope outputs",
            dependency="workflow envelope suppressed/abstained outputs",
        )
    abstained = 0
    total = 0
    for event in audit_events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        status = payload.get("status") or payload.get("recommended_action_type")
        if status is not None:
            total += 1
            if status in {"internal_only", "needs_data", "suppressed", "internal_only_packet"}:
                abstained += 1
    if total == 0:
        return MetricValue(
            "abstention_rate",
            None,
            "not_instrumented",
            "workflow envelope outputs",
            dependency="workflow envelope suppressed/abstained outputs",
        )
    return MetricValue(
        "abstention_rate",
        round(abstained / total, 4),
        "measured",
        "audit_ledger workflow packet payloads",
    )


def _category_for(*, action_type: str, intent: str) -> str:
    text = f"{intent} {action_type}".lower()
    if action_type == "recommend_next_best_action":
        return "internal_review"
    if action_type == "draft_customer_outreach":
        return "customer_outreach"
    if action_type == "log_crm_activity":
        return "crm_logging"
    if action_type == "update_cs_platform_record":
        return "cs_record_update"
    if action_type == "edit_success_plan":
        return "success_plan"
    if action_type == "initiate_customer_call":
        return "escalation_call"
    if "self_serve" in text:
        return "self_serve_activation"
    return action_type


def _event_category(event: AuditEvent) -> str:
    if event.event_type.startswith("self_serve_activation"):
        return "self_serve_activation"
    if event.event_type == "slot_b.draft":
        return "customer_outreach"
    return "book"


def _release_bucket(record: GateVerdictRecord) -> str:
    if record.autonomy_tier == 1:
        return "auto_internal"
    if record.autonomy_tier == 2:
        return "per_action_review"
    return "escalation_review"


def _share_dict(counts: Counter[str]) -> dict[str, dict[str, float | int]]:
    total = sum(counts.values())
    if total == 0:
        return {}
    return {
        key: {"count": count, "share": round(count / total, 4)}
        for key, count in sorted(counts.items())
    }


def _not_instrumented(name: str, source: str) -> MetricValue:
    return MetricValue(
        name,
        None,
        "not_instrumented",
        source,
        dependency=source,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verdict-fixture", type=Path, default=DEFAULT_VERDICT_FIXTURE)
    args = parser.parse_args()
    payload = build_fixture_scoreboard(
        output_path=args.output,
        verdict_fixture=args.verdict_fixture,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
