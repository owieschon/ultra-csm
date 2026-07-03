"""Validated org-knowledge pack for Slot B language and play selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ORG_PACK_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "org_pack.json"
ORG_CONTEXT_SCHEMA_VERSION = 1
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
class OrgPack:
    schema_version: int
    pack_version: str
    fictional: bool
    product_name: str
    terminology: dict[str, str]
    voice_rules: tuple[str, ...]
    value_props: tuple[ValueProp, ...]
    gap_plays: tuple[GapPlay, ...]

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


def load_org_pack(path: Path | str = DEFAULT_ORG_PACK_PATH) -> OrgPack:
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
    )
    if not pack.fictional:
        raise OrgPackError("default demo org pack must be marked fictional")
    if not pack.voice_rules or not pack.value_props or not pack.gap_plays:
        raise OrgPackError("org pack must include voice_rules, value_props, and gap_plays")
    return pack


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
