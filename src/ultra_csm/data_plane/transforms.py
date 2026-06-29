"""Shared raw-payload transform helpers for connector adapters."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


class TransformError(ValueError):
    """A raw connector payload cannot be transformed deterministically."""


_MISSING = object()


def get_path(payload: dict[str, Any], path: str, *, default: Any = _MISSING) -> Any:
    current: Any = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if default is not _MISSING:
            return default
        raise TransformError(f"missing required field: {path}")
    return current


def require_str(payload: dict[str, Any], path: str) -> str:
    value = get_path(payload, path)
    if value is None or value == "":
        raise TransformError(f"missing required string: {path}")
    if not isinstance(value, str):
        raise TransformError(f"expected string at {path}, got {type(value).__name__}")
    return value


def optional_str(payload: dict[str, Any], path: str) -> str | None:
    value = get_path(payload, path, default=None)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TransformError(f"expected optional string at {path}, got {type(value).__name__}")
    return value


def optional_bool(payload: dict[str, Any], path: str, *, default: bool) -> bool:
    value = get_path(payload, path, default=default)
    if isinstance(value, bool):
        return value
    raise TransformError(f"expected boolean at {path}, got {type(value).__name__}")


def money_to_cents(payload: dict[str, Any], path: str) -> int:
    value = get_path(payload, path)
    if value is None or value == "":
        raise TransformError(f"missing required money value: {path}")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TransformError(f"expected money value at {path}") from exc
    cents = (decimal * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)
