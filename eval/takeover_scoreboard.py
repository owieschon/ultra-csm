"""Read-only CSM takeover scoreboard.

The scoreboard is a measurement artifact, not a gate: it mirrors already
recorded audit/verdict/rejection state and labels each metric by source status.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

import psycopg

from ultra_csm.governance.csm_actions import CSM_ACTION_SPECS
from ultra_csm.platform.db import session
from ultra_csm.platform.seed import SEED_CLOCK
from ultra_csm.rejection_ledger import RejectionLedger, RejectionRecord

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "eval" / "takeover_scoreboard.json"
DEFAULT_REJECTION_GLOB = "week1_rejections_*.json"
DEFAULT_HUMAN_MINUTES_PER_VERDICT = 2.5
MetricStatus = Literal["measured", "modeled", "not_instrumented"]


@dataclass(frozen=True)
class VerdictRow:
    proposal_id: str
    category: str
    action: str
    autonomy_tier: int
    release_condition: str | None
    verdict: str


@dataclass(frozen=True)
class AuditSignal:
    event_type: str
    category: str | None
    account_ref: str | None
    payload: dict[str, Any]


def build_scoreboard(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    verdict_rows: Iterable[VerdictRow] = (),
    audit_signals: Iterable[AuditSignal] = (),
    rejection_records: Iterable[RejectionRecord] | None = None,
    rejection_paths: Iterable[Path] | None = None,
    verdict_source_available: bool = False,
    audit_source_available: bool = False,
    human_minutes_per_verdict: float = DEFAULT_HUMAN_MINUTES_PER_VERDICT,
) -> dict[str, Any]:
    verdicts = tuple(verdict_rows)
    signals = tuple(audit_signals)
    rejections = tuple(
        rejection_records
        if rejection_records is not None
        else load_rejection_records(rejection_paths)
    )
    rejection_source_available = bool(rejections)
    categories = _categories(verdicts, signals, rejections)

    rows = [
        _category_row(
            category,
            verdicts=verdicts,
            audit_signals=signals,
            rejection_records=rejections,
            verdict_source_available=verdict_source_available,
            audit_source_available=audit_source_available,
            rejection_source_available=rejection_source_available,
            human_minutes_per_verdict=human_minutes_per_verdict,
        )
        for category in categories
    ]
    rollup = _rollup(rows)
    artifact = {
        "name": "takeover_scoreboard",
        "measurement_scope": (
            "Read-only ledger analytics over observed gate verdicts, audit "
            "signals, and RejectionLedger records. Missing sources render as "
            "not_instrumented, never as zero."
        ),
        "claim_boundary": {
            "read_only": True,
            "mutates_gate": False,
            "mutates_ledger": False,
            "human_minutes_per_verdict_modeled": human_minutes_per_verdict,
        },
        "metric_status_values": ["measured", "modeled", "not_instrumented"],
        "source_summary": {
            "verdict_source_available": verdict_source_available,
            "audit_source_available": audit_source_available,
            "rejection_source_available": rejection_source_available,
            "verdict_count": len(verdicts),
            "audit_signal_count": len(signals),
            "rejection_count": len(rejections),
        },
        "rows": rows,
        "rollup": rollup,
    }
    _assert_metric_statuses(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def load_rejection_records(paths: Iterable[Path] | None = None) -> tuple[RejectionRecord, ...]:
    if paths is None:
        paths = sorted((REPO / "eval").glob(DEFAULT_REJECTION_GLOB))
    records: list[RejectionRecord] = []
    for path in paths:
        records.extend(RejectionLedger(path).all_records())
    return tuple(records)


def read_verdict_rows(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    now: Any = SEED_CLOCK,
) -> tuple[VerdictRow, ...]:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT p.proposal_id::text, p.intent, p.action, p.autonomy_tier, "
            "       v.verdict "
            "FROM action_proposal p "
            "JOIN action_verdict v ON v.proposal_id = p.proposal_id "
            "ORDER BY v.decided_ts, p.proposal_id"
        )
        rows = cur.fetchall()
    return tuple(
        VerdictRow(
            proposal_id=row[0],
            category=_category_from_action(action=row[2], intent=row[1]),
            action=row[2],
            autonomy_tier=int(row[3]),
            release_condition=_release_condition(row[2]),
            verdict=row[4],
        )
        for row in rows
    )


def read_audit_signals(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    limit: int = 1000,
    now: Any = SEED_CLOCK,
) -> tuple[AuditSignal, ...]:
    with session(conn, tenant_id=tenant_id, actor_id=actor_id, now=now) as cur:
        cur.execute(
            "SELECT event_type, account_ref, payload "
            "FROM audit.event_log "
            "ORDER BY ts DESC, event_id DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return tuple(
        AuditSignal(
            event_type=row[0],
            account_ref=row[1],
            payload=row[2] if isinstance(row[2], dict) else {},
            category=_category_from_payload(row[2] if isinstance(row[2], dict) else {}),
        )
        for row in rows
    )


def _category_row(
    category: str,
    *,
    verdicts: tuple[VerdictRow, ...],
    audit_signals: tuple[AuditSignal, ...],
    rejection_records: tuple[RejectionRecord, ...],
    verdict_source_available: bool,
    audit_source_available: bool,
    rejection_source_available: bool,
    human_minutes_per_verdict: float,
) -> dict[str, Any]:
    category_verdicts = tuple(row for row in verdicts if row.category == category)
    category_signals = tuple(signal for signal in audit_signals if signal.category == category)
    category_rejections = tuple(row for row in rejection_records if row.motion == category)
    return {
        "category": category,
        "metrics": {
            "coverage": _not_instrumented(
                "Packet count and accounts-in-scope are not committed on this baseline."
            ),
            "release_mix": _release_mix_metric(category, category_verdicts),
            "verdict_mix": _verdict_mix_metric(
                category_verdicts,
                source_available=verdict_source_available,
            ),
            "human_minutes_per_account_week": _human_minutes_metric(
                category_verdicts,
                source_available=verdict_source_available,
                minutes_per_verdict=human_minutes_per_verdict,
            ),
            "sampled_miss_rate": _not_instrumented(
                "Graduated-action sampled audits are not committed on this baseline."
            ),
            "denial_taxonomy": _denial_taxonomy_metric(
                category_rejections,
                source_available=rejection_source_available,
            ),
            "outcome_reconciliation_coverage": _outcome_metric(
                category_signals,
                source_available=audit_source_available,
            ),
            "abstention_rate": _not_instrumented(
                "Workflow-envelope abstain outputs are not wired into this ledger."
            ),
        },
    }


def _release_mix_metric(category: str, verdicts: tuple[VerdictRow, ...]) -> dict[str, Any]:
    policy = CSM_ACTION_SPECS.get(category)
    verdict_release_conditions = Counter(
        row.release_condition for row in verdicts if row.release_condition is not None
    )
    value: dict[str, Any] = {
        "policy_release_condition": policy.release_condition if policy else None,
        "policy_autonomy_tier": policy.autonomy_tier if policy else None,
        "observed_verdict_release_conditions": dict(verdict_release_conditions) or None,
    }
    return {
        "status": "measured",
        "value": value,
        "source": "src/ultra_csm/governance/csm_actions.py",
    }


def _verdict_mix_metric(
    verdicts: tuple[VerdictRow, ...],
    *,
    source_available: bool,
) -> dict[str, Any]:
    if not source_available:
        return _not_instrumented("No gate verdict source was supplied.")
    counts = Counter(row.verdict for row in verdicts)
    total = sum(counts.values())
    return {
        "status": "measured",
        "value": {
            "total": total,
            "counts": dict(counts),
            "rates": _rates(counts, total),
        },
        "source": "action_proposal JOIN action_verdict",
    }


def _human_minutes_metric(
    verdicts: tuple[VerdictRow, ...],
    *,
    source_available: bool,
    minutes_per_verdict: float,
) -> dict[str, Any]:
    if not source_available:
        return _not_instrumented("No gate verdict source was supplied.")
    return {
        "status": "modeled",
        "value": {
            "verdict_count": len(verdicts),
            "minutes_per_verdict": minutes_per_verdict,
            "human_minutes": round(len(verdicts) * minutes_per_verdict, 2),
        },
        "source": (
            "action_verdict count multiplied by configured per-verdict "
            "review-minute cost"
        ),
    }


def _denial_taxonomy_metric(
    records: tuple[RejectionRecord, ...],
    *,
    source_available: bool,
) -> dict[str, Any]:
    if not source_available:
        return _not_instrumented("No RejectionLedger source was found.")
    reasons = Counter(record.reason for record in records)
    return {
        "status": "measured",
        "value": {"total": sum(reasons.values()), "reasons": dict(reasons)},
        "source": f"eval/{DEFAULT_REJECTION_GLOB}",
    }


def _outcome_metric(
    signals: tuple[AuditSignal, ...],
    *,
    source_available: bool,
) -> dict[str, Any]:
    if not source_available:
        return _not_instrumented("No audit event source was supplied.")
    outcome_states = Counter(
        _outcome_state(signal.payload)
        for signal in signals
        if _outcome_state(signal.payload) is not None
    )
    if not outcome_states:
        return _not_instrumented(
            "Audit event source was present, but no outcome state was recorded."
        )
    total = sum(outcome_states.values())
    observed = total - outcome_states.get("unknown", 0) - outcome_states.get(
        "not_instrumented", 0
    )
    return {
        "status": "measured",
        "value": {
            "total": total,
            "states": dict(outcome_states),
            "observed_rate": round(observed / total, 3) if total else None,
        },
        "source": "audit.event_log payload outcome_state/realized_state",
    }


def _rollup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    for row in rows:
        for metric in row["metrics"].values():
            status_counts[metric["status"]] += 1
    return {
        "category_count": len(rows),
        "metric_status_counts": dict(status_counts),
        "headline": (
            "Current baseline measures policy release conditions and any "
            "present RejectionLedger taxonomy; packet coverage, sampled miss "
            "rate, abstention drift, and broad outcome reconciliation remain "
            "explicitly not_instrumented until their sources land."
        ),
    }


def _categories(
    verdicts: tuple[VerdictRow, ...],
    audit_signals: tuple[AuditSignal, ...],
    rejection_records: tuple[RejectionRecord, ...],
) -> list[str]:
    categories = set(CSM_ACTION_SPECS)
    categories.update(row.category for row in verdicts)
    categories.update(signal.category for signal in audit_signals if signal.category)
    categories.update(row.motion for row in rejection_records)
    return sorted(categories)


def _category_from_action(*, action: str, intent: str) -> str:
    if action in CSM_ACTION_SPECS:
        return action
    if intent in CSM_ACTION_SPECS:
        return intent
    return action or intent or "unknown"


def _category_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("motion", "workflow", "action", "recommended_action"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _release_condition(action: str) -> str | None:
    spec = CSM_ACTION_SPECS.get(action)
    return spec.release_condition if spec else None


def _outcome_state(payload: dict[str, Any]) -> str | None:
    for key in ("outcome_state", "realized_state", "outcome"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = value.get("realized_state") or value.get("state")
            if isinstance(nested, str) and nested:
                return nested
    return None


def _rates(counts: Counter[str], total: int) -> dict[str, float]:
    if total == 0:
        return {}
    return {
        key: round(value / total, 3)
        for key, value in sorted(counts.items())
    }


def _not_instrumented(dependency: str) -> dict[str, Any]:
    return {"status": "not_instrumented", "value": None, "dependency": dependency}


def _assert_metric_statuses(artifact: dict[str, Any]) -> None:
    allowed = set(artifact["metric_status_values"])
    for row in artifact["rows"]:
        for name, metric in row["metrics"].items():
            status = metric.get("status")
            if status not in allowed:
                raise ValueError(f"{row['category']}.{name} has invalid status {status!r}")
            if status == "not_instrumented" and metric.get("value") == 0:
                raise ValueError(f"{row['category']}.{name} renders missing source as zero")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dsn", help="optional psycopg connection string")
    parser.add_argument("--tenant-id", help="tenant id for DB reads")
    parser.add_argument("--actor-id", help="actor id for DB reads")
    parser.add_argument(
        "--human-minutes-per-verdict",
        type=float,
        default=DEFAULT_HUMAN_MINUTES_PER_VERDICT,
    )
    args = parser.parse_args(argv)

    verdicts: tuple[VerdictRow, ...] = ()
    signals: tuple[AuditSignal, ...] = ()
    verdict_source_available = False
    audit_source_available = False
    if args.dsn:
        if not args.tenant_id or not args.actor_id:
            parser.error("--dsn requires --tenant-id and --actor-id")
        with psycopg.connect(args.dsn) as conn:
            verdicts = read_verdict_rows(
                conn,
                tenant_id=args.tenant_id,
                actor_id=args.actor_id,
            )
            signals = read_audit_signals(
                conn,
                tenant_id=args.tenant_id,
                actor_id=args.actor_id,
            )
        verdict_source_available = True
        audit_source_available = True

    artifact = build_scoreboard(
        output_path=args.output,
        verdict_rows=verdicts,
        audit_signals=signals,
        verdict_source_available=verdict_source_available,
        audit_source_available=audit_source_available,
        human_minutes_per_verdict=args.human_minutes_per_verdict,
    )
    print(
        "takeover scoreboard: "
        f"{artifact['rollup']['category_count']} categories -> {args.output}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
