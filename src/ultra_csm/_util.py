"""Small shared helpers for the slim CSM spine."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any


def iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def compact_asdict(obj: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in asdict(obj).items()
        if value not in (None, (), [])
    }


def evidence_ids(evidence: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(ref.source_id for ref in evidence)
