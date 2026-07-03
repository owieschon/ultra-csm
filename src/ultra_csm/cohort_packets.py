"""Deterministic manager cohort rollups over existing customer-success data."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ultra_csm.data_plane import FixtureCustomerData

CLAIM_BOUNDARY: dict[str, bool] = {"sim": True, "live": False}

SEGMENT_AXES: tuple[str, ...] = ("size_band", "lifecycle_stage", "industry")
SIZE_BAND_ORDER: tuple[str, ...] = ("enterprise", "mid_market", "small_business")
HEALTH_BAND_ORDER: tuple[str, ...] = ("green", "yellow", "red", "unknown")
TRAJECTORY_ORDER: tuple[str, ...] = ("improving", "stable", "declining", "unknown")
HOLD_RELEASE_ORDER: tuple[str, ...] = ("held", "released")


@dataclass(frozen=True)
class ObservedDivergencePattern:
    pattern: str
    associated_account_count: int
    associated_account_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "associated_account_count": self.associated_account_count,
            "associated_account_ids": list(self.associated_account_ids),
        }


@dataclass(frozen=True)
class CohortRollupPacket:
    packet_id: str
    segment_axis: str
    segment_value: str
    associated_account_count: int
    associated_account_ids: tuple[str, ...]
    observed_health_band_distribution: dict[str, int]
    observed_trajectory_direction_counts: dict[str, int]
    observed_divergence_patterns: tuple[ObservedDivergencePattern, ...]
    observed_trigger_firing_counts: dict[str, int]
    observed_hold_release_counts: dict[str, int]
    observed_action_throughput: dict[str, int]
    observed_summary: str
    claim_boundary: dict[str, bool] = field(default_factory=lambda: dict(CLAIM_BOUNDARY))

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "segment_axis": self.segment_axis,
            "segment_value": self.segment_value,
            "associated_account_count": self.associated_account_count,
            "associated_account_ids": list(self.associated_account_ids),
            "observed_health_band_distribution": dict(self.observed_health_band_distribution),
            "observed_trajectory_direction_counts": dict(
                self.observed_trajectory_direction_counts
            ),
            "observed_divergence_patterns": [
                pattern.to_dict() for pattern in self.observed_divergence_patterns
            ],
            "observed_trigger_firing_counts": dict(self.observed_trigger_firing_counts),
            "observed_hold_release_counts": dict(self.observed_hold_release_counts),
            "observed_action_throughput": dict(self.observed_action_throughput),
            "observed_summary": self.observed_summary,
            "claim_boundary": dict(self.claim_boundary),
        }


def size_band_for_arr(arr_cents: int | None) -> str:
    """Return a stable ARR size band for segmenting manager views."""

    value = arr_cents or 0
    if value >= 20_000_000:
        return "enterprise"
    if value >= 5_000_000:
        return "mid_market"
    return "small_business"


def build_cohort_rollup_packets(
    data: FixtureCustomerData,
    *,
    snapshots: Any | None = None,
    divergence_patterns: Any | None = None,
    tick_ledger: Any | None = None,
    action_packets: Any | None = None,
    trajectory_window_days: int = 365,
) -> tuple[CohortRollupPacket, ...]:
    """Build deterministic cohort packets from fixture data and optional artifacts."""

    accounts = {account.account_id: account for account in data.accounts}
    companies = {company.company_id: company for company in data.companies}
    health = {score.account_id: score for score in data.health_scores}
    account_ids = tuple(sorted(set(accounts) | set(companies)))

    segment_members = _segment_members(account_ids, accounts, companies)
    trajectory_by_account = _trajectory_by_account(snapshots, trajectory_window_days)
    divergence_by_account = _divergence_by_account(divergence_patterns)
    if trajectory_by_account is not None:
        _add_observed_health_trajectory_patterns(
            divergence_by_account,
            account_ids,
            health,
            trajectory_by_account,
        )
    trigger_by_account, hold_release_by_account = _ledger_counts_by_account(tick_ledger)
    action_by_account = _action_counts_by_account(action_packets)

    packets: list[CohortRollupPacket] = []
    for axis in SEGMENT_AXES:
        for value, members in _ordered_segments(axis, segment_members[axis]):
            packet = _packet_for_segment(
                axis=axis,
                value=value,
                account_ids=members,
                health=health,
                trajectory_by_account=trajectory_by_account,
                divergence_by_account=divergence_by_account,
                trigger_by_account=trigger_by_account,
                hold_release_by_account=hold_release_by_account,
                action_by_account=action_by_account,
            )
            packets.append(packet)
    return tuple(packets)


def build_cohort_packets_artifact(
    data: FixtureCustomerData,
    *,
    snapshots: Any | None = None,
    divergence_patterns: Any | None = None,
    tick_ledger: Any | None = None,
    action_packets: Any | None = None,
    trajectory_window_days: int = 365,
    output_path: Path | None = None,
) -> dict[str, Any]:
    packets = build_cohort_rollup_packets(
        data,
        snapshots=snapshots,
        divergence_patterns=divergence_patterns,
        tick_ledger=tick_ledger,
        action_packets=action_packets,
        trajectory_window_days=trajectory_window_days,
    )
    artifact = {
        "artifact": "cohort_packets",
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "packet_count": len(packets),
        "segment_axes": list(SEGMENT_AXES),
        "packets": [packet.to_dict() for packet in packets],
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_stable_json(artifact), encoding="utf-8")
    return artifact


def artifact_sha256(artifact: Mapping[str, Any]) -> str:
    return hashlib.sha256(_stable_json(artifact).encode("utf-8")).hexdigest()


def _packet_for_segment(
    *,
    axis: str,
    value: str,
    account_ids: tuple[str, ...],
    health: Mapping[str, Any],
    trajectory_by_account: Mapping[str, str] | None,
    divergence_by_account: Mapping[str, set[str]],
    trigger_by_account: Mapping[str, Counter[str]],
    hold_release_by_account: Mapping[str, Counter[str]],
    action_by_account: Mapping[str, Counter[str]],
) -> CohortRollupPacket:
    health_counts = _ordered_counter(
        (
            _known_or_unknown(getattr(health.get(account_id), "band", None))
            for account_id in account_ids
        ),
        HEALTH_BAND_ORDER,
    )
    if trajectory_by_account is None:
        trajectory_counts: dict[str, int] = {}
    else:
        trajectory_counts = _ordered_counter(
            (
                _known_or_unknown(trajectory_by_account.get(account_id))
                for account_id in account_ids
            ),
            TRAJECTORY_ORDER,
        )
    divergence_patterns = _aggregate_divergence_patterns(account_ids, divergence_by_account)
    trigger_counts = _merged_counts(account_ids, trigger_by_account)
    hold_release_counts = _ordered_counter(
        _expanded_counts(account_ids, hold_release_by_account),
        HOLD_RELEASE_ORDER,
    )
    action_counts = _merged_counts(account_ids, action_by_account)
    return CohortRollupPacket(
        packet_id=_packet_id(axis, value),
        segment_axis=axis,
        segment_value=value,
        associated_account_count=len(account_ids),
        associated_account_ids=account_ids,
        observed_health_band_distribution=health_counts,
        observed_trajectory_direction_counts=trajectory_counts,
        observed_divergence_patterns=divergence_patterns,
        observed_trigger_firing_counts=trigger_counts,
        observed_hold_release_counts=hold_release_counts,
        observed_action_throughput=action_counts,
        observed_summary=_summary(
            axis,
            value,
            len(account_ids),
            health_counts,
            trajectory_counts,
            divergence_patterns,
            trigger_counts,
            action_counts,
        ),
    )


def _segment_members(
    account_ids: tuple[str, ...],
    accounts: Mapping[str, Any],
    companies: Mapping[str, Any],
) -> dict[str, dict[str, tuple[str, ...]]]:
    by_axis: dict[str, dict[str, list[str]]] = {
        axis: defaultdict(list) for axis in SEGMENT_AXES
    }
    for account_id in account_ids:
        account = accounts.get(account_id)
        company = companies.get(account_id)
        industry = (
            getattr(account, "industry", None)
            or getattr(company, "industry", None)
            or "unknown"
        )
        values = {
            "size_band": size_band_for_arr(getattr(company, "arr_cents", None)),
            "lifecycle_stage": _known_or_unknown(getattr(company, "lifecycle_stage", None)),
            "industry": _known_or_unknown(industry),
        }
        for axis, value in values.items():
            by_axis[axis][value].append(account_id)
    return {
        axis: {value: tuple(sorted(ids)) for value, ids in values.items()}
        for axis, values in by_axis.items()
    }


def _ordered_segments(
    axis: str,
    values: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if axis == "size_band":
        order = {value: index for index, value in enumerate(SIZE_BAND_ORDER)}

        def size_key(item: tuple[str, tuple[str, ...]]) -> tuple[int, str]:
            return order.get(item[0], len(order)), item[0]

        return tuple(sorted(values.items(), key=size_key))

    def value_key(item: tuple[str, tuple[str, ...]]) -> str:
        return item[0]

    return tuple(sorted(values.items(), key=value_key))


def _trajectory_by_account(
    snapshots: Any | None,
    window_days: int,
) -> dict[str, str] | None:
    if snapshots is None:
        return None
    if hasattr(snapshots, "all_account_ids") and hasattr(snapshots, "compute_trend"):
        return {
            account_id: _known_or_unknown(snapshots.compute_trend(account_id, window_days))
            for account_id in sorted(snapshots.all_account_ids())
        }
    if isinstance(snapshots, Mapping):
        return _trajectory_from_mapping(snapshots)
    points_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in _records(snapshots):
        account_id = _record_account_id(record)
        if account_id:
            points_by_account[account_id].append(record)
    return {
        account_id: _trend_from_points(points)
        for account_id, points in sorted(points_by_account.items())
    }


def _trajectory_from_mapping(payload: Mapping[str, Any]) -> dict[str, str]:
    if "accounts" in payload:
        return _trajectory_by_account(payload["accounts"], 365) or {}
    if "snapshots" in payload and isinstance(payload["snapshots"], Iterable):
        return _trajectory_by_account(payload["snapshots"], 365) or {}
    out: dict[str, str] = {}
    for account_id, value in payload.items():
        if not isinstance(account_id, str):
            continue
        record = _record(value)
        trajectory = _record(record.get("trajectory")) if isinstance(record, Mapping) else {}
        trend = record.get("trend") or trajectory.get("trend")
        if isinstance(trend, str):
            out[account_id] = _known_or_unknown(trend)
            continue
        points = record.get("snapshots") if isinstance(record, Mapping) else None
        if isinstance(points, Iterable):
            out[account_id] = _trend_from_points([_record(point) for point in points])
    return out


def _trend_from_points(points: Iterable[Mapping[str, Any]]) -> str:
    ordered = sorted(
        (
            point for point in points
            if "health_score" in point and _coerce_float(point.get("health_score")) is not None
        ),
        key=lambda point: _coerce_int(point.get("day")) or 0,
    )
    if len(ordered) < 2:
        return "unknown"
    first = _coerce_float(ordered[0].get("health_score"))
    last = _coerce_float(ordered[-1].get("health_score"))
    if first is None or last is None:
        return "unknown"
    delta = last - first
    if delta > 5.0:
        return "improving"
    if delta < -5.0:
        return "declining"
    return "stable"


def _divergence_by_account(payload: Any | None) -> dict[str, set[str]]:
    by_account: dict[str, set[str]] = defaultdict(set)
    if payload is None:
        return by_account
    for record in _records(payload):
        account_id = _record_account_id(record)
        pattern = (
            record.get("pattern")
            or record.get("name")
            or record.get("factor")
            or record.get("divergence")
        )
        if account_id and isinstance(pattern, str) and pattern.strip():
            by_account[account_id].add(_slug(pattern))
    return by_account


def _add_observed_health_trajectory_patterns(
    by_account: dict[str, set[str]],
    account_ids: tuple[str, ...],
    health: Mapping[str, Any],
    trajectory_by_account: Mapping[str, str],
) -> None:
    for account_id in account_ids:
        band = getattr(health.get(account_id), "band", None)
        trend = trajectory_by_account.get(account_id)
        if band == "green" and trend == "declining":
            by_account[account_id].add("observed_green_band_declining_trajectory")


def _ledger_counts_by_account(payload: Any | None) -> tuple[
    dict[str, Counter[str]],
    dict[str, Counter[str]],
]:
    trigger_counts: dict[str, Counter[str]] = defaultdict(Counter)
    hold_release_counts: dict[str, Counter[str]] = defaultdict(Counter)
    if payload is None:
        return trigger_counts, hold_release_counts
    for record in _records(payload):
        account_id = _record_account_id(record)
        if not account_id:
            continue
        trigger_name = record.get("trigger_name") or record.get("name")
        if isinstance(trigger_name, str) and trigger_name.strip():
            trigger_counts[account_id][_slug(trigger_name)] += 1
        event = _event_name(record)
        if event is None:
            continue
        if "release" in event:
            hold_release_counts[account_id]["released"] += 1
        elif "held" in event or "hold" in event:
            hold_release_counts[account_id]["held"] += 1
    return trigger_counts, hold_release_counts


def _action_counts_by_account(payload: Any | None) -> dict[str, Counter[str]]:
    by_account: dict[str, Counter[str]] = defaultdict(Counter)
    if payload is None:
        return by_account
    for record in _records(payload):
        account_id = _record_account_id(record)
        if not account_id:
            nested = _record(record.get("payload"))
            account_id = _record_account_id(nested)
        proposal = _record(record.get("proposal"))
        source = proposal if proposal else record
        status = source.get("status") or source.get("proposal_status") or record.get("verdict")
        if account_id and isinstance(status, str) and status.strip():
            by_account[account_id][_slug(status)] += 1
    return by_account


def _aggregate_divergence_patterns(
    account_ids: tuple[str, ...],
    by_account: Mapping[str, set[str]],
) -> tuple[ObservedDivergencePattern, ...]:
    accounts_by_pattern: dict[str, list[str]] = defaultdict(list)
    for account_id in account_ids:
        for pattern in sorted(by_account.get(account_id, ())):
            accounts_by_pattern[pattern].append(account_id)
    return tuple(
        ObservedDivergencePattern(
            pattern=pattern,
            associated_account_count=len(ids),
            associated_account_ids=tuple(sorted(ids)),
        )
        for pattern, ids in sorted(accounts_by_pattern.items())
    )


def _records(payload: Any) -> tuple[dict[str, Any], ...]:
    if payload is None:
        return ()
    if isinstance(payload, Mapping):
        return _records_from_mapping(payload)
    if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
        records = []
        for item in payload:
            records.extend(_records(item))
        return tuple(records)
    record = _record(payload)
    return _records_from_mapping(record) if record else ()


def _records_from_mapping(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    nested_keys = (
        "fired_triggers",
        "ledger",
        "events",
        "entries",
        "items",
        "work_items",
        "actions",
        "proposals",
        "packets",
    )
    records: list[dict[str, Any]] = []
    for key in nested_keys:
        value = payload.get(key)
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            records.extend(_records(value))
    if _looks_like_record(payload):
        records.append(_record(payload))
    return tuple(records)


def _record(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return _record(value.to_dict())
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _looks_like_record(value: Mapping[str, Any]) -> bool:
    return bool({
        "account_id",
        "trigger_name",
        "event_type",
        "event",
        "status",
        "proposal",
        "pattern",
        "name",
        "factor",
        "health_score",
    } & set(value))


def _record_account_id(record: Mapping[str, Any]) -> str | None:
    value = (
        record.get("account_id")
        or record.get("company_id")
        or record.get("customer_id")
    )
    if isinstance(value, str) and value.strip():
        return value
    nested = record.get("account")
    if isinstance(nested, Mapping):
        nested_value = nested.get("account_id") or nested.get("id")
        if isinstance(nested_value, str) and nested_value.strip():
            return nested_value
    return None


def _event_name(record: Mapping[str, Any]) -> str | None:
    value = record.get("event_type") or record.get("event") or record.get("type")
    return _slug(value) if isinstance(value, str) and value.strip() else None


def _merged_counts(
    account_ids: tuple[str, ...],
    by_account: Mapping[str, Counter[str]],
) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for account_id in account_ids:
        counter.update(by_account.get(account_id, Counter()))
    return {key: counter[key] for key in sorted(counter)}


def _expanded_counts(
    account_ids: tuple[str, ...],
    by_account: Mapping[str, Counter[str]],
) -> tuple[str, ...]:
    values: list[str] = []
    for account_id in account_ids:
        for key, count in by_account.get(account_id, Counter()).items():
            values.extend([key] * count)
    return tuple(values)


def _ordered_counter(values: Iterable[str], order: tuple[str, ...]) -> dict[str, int]:
    counter = Counter(values)
    out = {key: counter.get(key, 0) for key in order}
    for key in sorted(set(counter) - set(order)):
        out[key] = counter[key]
    return out


def _summary(
    axis: str,
    value: str,
    account_count: int,
    health_counts: Mapping[str, int],
    trajectory_counts: Mapping[str, int],
    divergence_patterns: tuple[ObservedDivergencePattern, ...],
    trigger_counts: Mapping[str, int],
    action_counts: Mapping[str, int],
) -> str:
    parts = [
        f"Observed {account_count} simulated accounts for {axis}={value}",
        f"health bands {_compact_counts(health_counts)}",
    ]
    if trajectory_counts:
        parts.append(f"trajectory directions {_compact_counts(trajectory_counts)}")
    if divergence_patterns:
        pattern_text = ", ".join(
            f"{item.pattern}:{item.associated_account_count}"
            for item in divergence_patterns
        )
        parts.append(f"associated divergence patterns {pattern_text}")
    if trigger_counts:
        parts.append(f"associated trigger firings {_compact_counts(trigger_counts)}")
    if action_counts:
        parts.append(f"observed action statuses {_compact_counts(action_counts)}")
    return "; ".join(parts) + "."


def _compact_counts(counts: Mapping[str, int]) -> str:
    nonzero = [(key, value) for key, value in counts.items() if value]
    if not nonzero:
        return "none"
    return ", ".join(f"{key}:{value}" for key, value in nonzero)


def _known_or_unknown(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    return _slug(value)


def _packet_id(axis: str, value: str) -> str:
    return f"cohort:{_slug(axis)}:{_slug(value)}"


def _slug(value: Any) -> str:
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text or "unknown"


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
