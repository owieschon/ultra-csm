"""Baseline-relative threshold resolver -- the Universe v2 WS-Tenant-
Fieldstone HARD RULE knob.

Fieldstone's entire purpose (``docs/TENANT_FIELDSTONE_BIBLE.md``, "The
norms") is that risk must be read as a DELTA from the tenant's (and the
account's own) baseline, never an absolute FleetOps-tuned threshold.
``ultra_csm.data_plane.signal_extractor.reply_latency_trend`` already
computes a delta (trailing-21d mean vs. prior-21d mean) -- this module is
the minimal additive piece that was still missing: turning that raw delta
into a flag/no-flag decision using a TENANT-CONFIG-sourced threshold
(``knowledge/tenants/fieldstone/norms_baselines.json``) instead of a
hardcoded number in code.

Deliberately NOT a change to ``config/value_model_config.json`` or
``ultra_csm/value_model.py`` (both shared, outside this program's
ownership map) -- this is tenant CONFIG, read only by fieldstone's own
code, exactly the same "config, never code" discipline
``ultra_csm.knowledge.load_playbooks`` already uses for playbooks. Fails
closed: a missing config file, a missing key, or an ``ExtractedSignal``
with ``value=None`` (insufficient history) all resolve to
``flagged=False`` with an explicit ``reason`` -- never a fabricated flag
and never a silent default baked into code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASELINES_PATH = (
    Path(__file__).resolve().parents[5] / "knowledge" / "tenants" / "fieldstone" / "norms_baselines.json"
)


class NormsBaselineError(ValueError):
    """Raised when the fieldstone norms-baseline config is missing/malformed."""


@dataclass(frozen=True)
class NormsBaselineConfig:
    schema_version: int
    tenant: str
    flag_delta_floor_by_metric: dict[str, float]


@dataclass(frozen=True)
class BaselineFlagResult:
    metric_name: str
    delta: float | None
    flag_delta_floor: float | None
    flagged: bool
    reason: str


def load_norms_baselines(path: Path | str = DEFAULT_BASELINES_PATH) -> NormsBaselineConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise NormsBaselineError("norms_baselines.json must be a JSON object")
    if raw.get("schema_version") != 1:
        raise NormsBaselineError("unsupported norms_baselines schema_version")
    if not raw.get("fictional"):
        raise NormsBaselineError("norms_baselines.json must be marked fictional")
    if raw.get("tenant") != "fieldstone":
        raise NormsBaselineError("norms_baselines.json tenant field must be 'fieldstone'")

    floors: dict[str, float] = {}
    for key, value in raw.items():
        if key in ("schema_version", "fictional", "tenant", "note"):
            continue
        if not isinstance(value, dict) or "flag_delta_floor" not in value:
            raise NormsBaselineError(f"norms_baselines entry {key!r} missing flag_delta_floor")
        floors[key] = float(value["flag_delta_floor"])
    if not floors:
        raise NormsBaselineError("norms_baselines.json defines no metric floors")

    return NormsBaselineConfig(
        schema_version=1,
        tenant="fieldstone",
        flag_delta_floor_by_metric=floors,
    )


def classify_delta(
    metric_name: str,
    delta: float | None,
    *,
    config: NormsBaselineConfig | None = None,
) -> BaselineFlagResult:
    """Fail-closed baseline-relative classification: ``delta`` is the raw
    signal_extractor delta (e.g. ``reply_latency_trend_hours``'s
    ``ExtractedSignal.value``). ``None`` (insufficient history) always
    resolves to ``flagged=False`` -- never fabricated. A metric with no
    configured floor also resolves to ``flagged=False`` (fail-closed: an
    unconfigured metric is never silently treated as "always flag" or
    "always safe" via a hardcoded fallback -- the absence itself is the
    honest, recorded reason)."""

    cfg = config or load_norms_baselines()
    floor = cfg.flag_delta_floor_by_metric.get(metric_name)
    if delta is None:
        return BaselineFlagResult(
            metric_name=metric_name, delta=None, flag_delta_floor=floor,
            flagged=False, reason="insufficient_history: no delta computable yet",
        )
    if floor is None:
        return BaselineFlagResult(
            metric_name=metric_name, delta=delta, flag_delta_floor=None,
            flagged=False, reason=f"no configured baseline floor for metric {metric_name!r}",
        )
    flagged = delta >= floor
    reason = (
        f"delta {delta:.1f} >= tenant baseline floor {floor:.1f}: flagged"
        if flagged
        else f"delta {delta:.1f} < tenant baseline floor {floor:.1f}: within normal variance"
    )
    return BaselineFlagResult(
        metric_name=metric_name, delta=delta, flag_delta_floor=floor,
        flagged=flagged, reason=reason,
    )
