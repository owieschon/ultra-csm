"""Small shared helpers for the slim CSM spine."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict
from datetime import date
from typing import Any

_NON_PERSON_OPENERS = frozenset({
    "mr", "mrs", "ms", "miss", "dr", "prof", "sir", "mx",
    "support", "sales", "info", "admin", "team", "customer", "unknown", "none",
})


def iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def customer_greeting(display_name: str | None) -> str:
    """Use the first token of a given-name-first display name, or a neutral opener.

    The current contact contract has no preferred/given-name field. This
    heuristic cannot infer name order or compound given names. Recognized
    titles, role inbox labels, initials and malformed tokens use "Hi,".
    """
    if not display_name:
        return "Hi,"
    stripped = display_name.strip()
    if not stripped:
        return "Hi,"
    first = stripped.split()[0]
    if first.casefold().rstrip(".") in _NON_PERSON_OPENERS:
        return "Hi,"
    parts = re.split("['’-]", unicodedata.normalize("NFC", first))
    if any(not part.isalpha() for part in parts) or len("".join(parts)) < 2:
        return "Hi,"
    return f"Hi {first},"


def compact_asdict(obj: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in asdict(obj).items()
        if value not in (None, (), [])
    }


def evidence_ids(evidence: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(ref.source_id for ref in evidence)
