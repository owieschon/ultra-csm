"""Validated org-knowledge pack for Slot B language and play selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ORG_PACK_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "org_pack.json"
DEFAULT_GOLDEN_CORPUS_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "golden_corpus"
DEFAULT_TENANTS_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "tenants"
ORG_CONTEXT_SCHEMA_VERSION = 1
PLAYBOOK_SCHEMA_VERSION = 1
PLAYBOOK_SERVICE_TIERS = ("high_touch", "mid_touch", "tech_touch")
PLAYBOOK_MOTIONS = (
    "personal_email",
    "working_session",
    "qbr",
    "escalation",
    "campaign_enroll",
    "content_route",
    "cohort_action",
)
_FORBIDDEN_KEYS = {
    "account_id",
    "account_name",
    "as_of",
    "autonomy_tier",
    "contact_email",
    "contact_name",
    "customer_contact_allowed",
    "disposition",
    "evidence",
    "priority",
    "recommended_action",
    "required_permission",
}
_UNSAFE_CUSTOMER_ASK_TERMS = (
    "approval",
    "approve",
    "approved",
    "commercial terms",
    "contract",
    "copy the",
    "discount",
    "escalate to",
    "guarantee",
)


class OrgPackError(ValueError):
    """Raised when the org-knowledge pack is missing required shape."""


@dataclass(frozen=True)
class GapPlay:
    factor: str
    play: str
    customer_ask: str


@dataclass(frozen=True)
class ValueProp:
    id: str
    name: str
    summary: str


@dataclass(frozen=True)
class GoldenExample:
    """One reference artifact from ``knowledge/golden_corpus/`` -- exemplar
    prose an author or reviewer can compare drafted content against. Not
    yet wired into ``slot_b_context()``: doing so needs more than a
    pass-through (which exemplar is relevant to a given draft, token
    budget), so it is surfaced on ``OrgPack`` and left for a future wiring
    decision rather than half-wired here."""

    kind: str
    title: str
    content: str


@dataclass(frozen=True)
class OrgPack:
    schema_version: int
    pack_version: str
    fictional: bool
    product_name: str
    terminology: dict[str, str]
    voice_rules: tuple[str, ...]
    value_props: tuple[ValueProp, ...]
    gap_plays: tuple[GapPlay, ...]
    golden_corpus: tuple[GoldenExample, ...] = ()

    def slot_b_context(self) -> dict[str, Any]:
        """Return the compact context included in Slot B requests."""

        return {
            "schema_version": ORG_CONTEXT_SCHEMA_VERSION,
            "pack_version": self.pack_version,
            "fictional": self.fictional,
            "product_name": self.product_name,
            "terminology": self.terminology,
            "voice_rules": list(self.voice_rules),
            "value_props": [
                {"id": prop.id, "name": prop.name, "summary": prop.summary}
                for prop in self.value_props
            ],
            "gap_plays": [
                {
                    "factor": play.factor,
                    "play": play.play,
                    "customer_ask": play.customer_ask,
                }
                for play in self.gap_plays
            ],
            "boundary": (
                "Org context may shape language and play selection only; "
                "customer-specific claims still require request evidence."
            ),
        }


def load_org_pack(
    path: Path | str = DEFAULT_ORG_PACK_PATH,
    *,
    corpus_dir: Path | str = DEFAULT_GOLDEN_CORPUS_DIR,
) -> OrgPack:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise OrgPackError("org pack must be a JSON object")
    _reject_forbidden_keys(raw)
    schema_version = _required_int(raw, "schema_version")
    if schema_version != ORG_CONTEXT_SCHEMA_VERSION:
        raise OrgPackError(f"unsupported org pack schema_version: {schema_version}")
    pack = OrgPack(
        schema_version=schema_version,
        pack_version=_required_str(raw, "pack_version"),
        fictional=_required_bool(raw, "fictional"),
        product_name=_required_str(raw, "product_name"),
        terminology=_string_map(raw, "terminology"),
        voice_rules=_string_tuple(raw, "voice_rules"),
        value_props=tuple(_value_prop(item) for item in _required_list(raw, "value_props")),
        gap_plays=tuple(_gap_play(item) for item in _required_list(raw, "gap_plays")),
        golden_corpus=_load_golden_corpus(Path(corpus_dir)),
    )
    if not pack.fictional:
        raise OrgPackError("default demo org pack must be marked fictional")
    if not pack.voice_rules or not pack.value_props or not pack.gap_plays:
        raise OrgPackError("org pack must include voice_rules, value_props, and gap_plays")
    return pack


class PlaybookError(ValueError):
    """Raised when a tenant playbook file is missing required shape."""


@dataclass(frozen=True)
class ServiceTier:
    tier: str
    rule: dict[str, Any]
    allowed_motions: tuple[str, ...]
    forbidden_motions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Play:
    id: str
    trigger_factor: str
    motion: str
    tiers: tuple[str, ...]
    content_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlaybookSet:
    schema_version: int
    fictional: bool
    tenant: str
    service_tiers: tuple[ServiceTier, ...]
    plays: tuple[Play, ...]

    def tier_for(self, tier_name: str) -> ServiceTier:
        for service_tier in self.service_tiers:
            if service_tier.tier == tier_name:
                return service_tier
        raise PlaybookError(f"unknown service tier: {tier_name}")


def load_playbooks(
    tenant_slug: str,
    *,
    tenants_dir: Path | str = DEFAULT_TENANTS_DIR,
) -> PlaybookSet:
    """Load and validate ``knowledge/tenants/<tenant_slug>/playbooks.json``.

    Fail-closed, same discipline as :func:`load_org_pack`: unknown tier/motion
    names, a missing ``"fictional": true``, or a play referencing an
    undefined tier all raise :class:`PlaybookError` rather than loading
    partially-valid data.
    """

    path = Path(tenants_dir) / tenant_slug / "playbooks.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PlaybookError("playbook file must be a JSON object")
    schema_version = _required_int(raw, "schema_version")
    if schema_version != PLAYBOOK_SCHEMA_VERSION:
        raise PlaybookError(f"unsupported playbook schema_version: {schema_version}")
    if not _required_bool(raw, "fictional"):
        raise PlaybookError("playbook file must be marked fictional")
    tenant = _required_str(raw, "tenant")
    if tenant != tenant_slug:
        raise PlaybookError(f"playbook tenant field {tenant!r} does not match {tenant_slug!r}")

    service_tiers = tuple(_service_tier(item) for item in _required_list(raw, "service_tiers"))
    tier_names = {service_tier.tier for service_tier in service_tiers}
    plays = tuple(_play(item, tier_names) for item in _required_list(raw, "plays"))

    return PlaybookSet(
        schema_version=schema_version,
        fictional=True,
        tenant=tenant,
        service_tiers=service_tiers,
        plays=plays,
    )


def _service_tier(raw: Any) -> ServiceTier:
    if not isinstance(raw, dict):
        raise PlaybookError("service_tiers entries must be objects")
    tier = _required_str(raw, "tier")
    if tier not in PLAYBOOK_SERVICE_TIERS:
        raise PlaybookError(f"unknown service tier: {tier}")
    rule = raw.get("rule")
    if not isinstance(rule, dict) or not rule:
        raise PlaybookError(f"service tier {tier} missing a rule object")
    allowed = _string_tuple(raw, "allowed_motions")
    _validate_motions(allowed, context=f"service tier {tier} allowed_motions")
    forbidden = tuple(raw.get("forbidden_motions", ()))
    _validate_motions(forbidden, context=f"service tier {tier} forbidden_motions")
    return ServiceTier(tier=tier, rule=rule, allowed_motions=allowed, forbidden_motions=forbidden)


def _play(raw: Any, tier_names: set[str]) -> Play:
    if not isinstance(raw, dict):
        raise PlaybookError("plays entries must be objects")
    motion = _required_str(raw, "motion")
    _validate_motions((motion,), context="play motion")
    tiers = _string_tuple(raw, "tiers")
    for tier in tiers:
        if tier not in tier_names:
            raise PlaybookError(f"play references undefined service tier: {tier}")
    content_refs = tuple(raw.get("content_refs", ()))
    return Play(
        id=_required_str(raw, "id"),
        trigger_factor=_required_str(raw, "trigger_factor"),
        motion=motion,
        tiers=tiers,
        content_refs=content_refs,
    )


def _validate_motions(motions: tuple[str, ...], *, context: str) -> None:
    for motion in motions:
        if motion not in PLAYBOOK_MOTIONS:
            raise PlaybookError(f"{context}: unknown motion {motion}")


def _load_golden_corpus(corpus_dir: Path) -> tuple[GoldenExample, ...]:
    """Load every ``*.json`` exemplar in *corpus_dir*. A missing directory is
    not an error -- the corpus is optional -- but a present, malformed file
    fails closed with the filename in the error, never silently skipped."""

    if not corpus_dir.is_dir():
        return ()
    examples: list[GoldenExample] = []
    for file_path in sorted(corpus_dir.glob("*.json")):
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise OrgPackError("golden corpus file must be a JSON object")
            _reject_forbidden_keys(raw)
            if not _required_bool(raw, "fictional"):
                raise OrgPackError("golden corpus file must be marked fictional")
            examples.append(
                GoldenExample(
                    kind=_required_str(raw, "kind"),
                    title=_required_str(raw, "title"),
                    content=_required_str(raw, "content"),
                )
            )
        except (OrgPackError, json.JSONDecodeError) as exc:
            raise OrgPackError(f"golden corpus file {file_path.name}: {exc}") from exc
    return tuple(examples)


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in _FORBIDDEN_KEYS:
                raise OrgPackError(f"org pack contains runtime field: {key}")
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _value_prop(raw: Any) -> ValueProp:
    if not isinstance(raw, dict):
        raise OrgPackError("value_props entries must be objects")
    _reject_forbidden_keys(raw)
    return ValueProp(
        id=_required_str(raw, "id"),
        name=_required_str(raw, "name"),
        summary=_required_str(raw, "summary"),
    )


def _gap_play(raw: Any) -> GapPlay:
    if not isinstance(raw, dict):
        raise OrgPackError("gap_plays entries must be objects")
    _reject_forbidden_keys(raw)
    customer_ask = _required_str(raw, "customer_ask")
    if not is_safe_customer_ask(customer_ask):
        raise OrgPackError("gap play customer_ask contains unsafe authority language")
    return GapPlay(
        factor=_required_str(raw, "factor"),
        play=_required_str(raw, "play"),
        customer_ask=customer_ask,
    )


def is_safe_customer_ask(value: str) -> bool:
    text = value.lower()
    return not any(term in text for term in _UNSAFE_CUSTOMER_ASK_TERMS)


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OrgPackError(f"org pack missing required string: {key}")
    return value


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise OrgPackError(f"org pack missing required boolean: {key}")
    return value


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise OrgPackError(f"org pack missing required integer: {key}")
    return value


def _required_list(raw: dict[str, Any], key: str) -> list[Any]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise OrgPackError(f"org pack missing required list: {key}")
    return value


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    values = _required_list(raw, key)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise OrgPackError(f"org pack list must contain only strings: {key}")
    return tuple(values)


def _string_map(raw: dict[str, Any], key: str) -> dict[str, str]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise OrgPackError(f"org pack missing required object: {key}")
    if not all(
        isinstance(k, str)
        and k.strip()
        and isinstance(v, str)
        and v.strip()
        for k, v in value.items()
    ):
        raise OrgPackError(f"org pack object must map strings to strings: {key}")
    return dict(value)
