"""Loader + validator for the Universe v2 expected-actions gold set.

See ``eval/gold/expected_actions_schema.md`` for the row shape and the
anti-Goodhart note: this file is graded against
``docs/SYNTHETIC_UNIVERSE_BIBLE.md``, never the other way around.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultra_csm.data_plane.synthetic_book import _ACCT_DATA
from ultra_csm.data_plane.tenants.crateworks.book import ACCOUNTS as _CRATEWORKS_ACCT_DATA
from ultra_csm.knowledge import PLAYBOOK_MOTIONS

# Additive union across tenants (Universe v2, Wave 3): this loader started
# fleetops-only; WS-Tenant-Crateworks widened it to also recognize
# crateworks' own account slugs, so `crateworks_expected_actions.json` can
# validate through the SAME shared loader rather than forking a second one.
# fleetops' own slug set and validation behavior are unchanged (still the
# only tenant `tests/test_expected_actions_gold.py` exercises).
_KNOWN_ACCOUNT_SLUGS = frozenset(slug for slug, *_ in _ACCT_DATA) | frozenset(
    slug for slug, *_ in _CRATEWORKS_ACCT_DATA
)

GOLD_DIR = Path(__file__).resolve().parent / "gold"
GRADING_MODES = ("shadow", "gap", "none")


class ExpectedActionsGoldError(ValueError):
    """Raised when an expected-actions gold row is malformed."""


@dataclass(frozen=True)
class ExpectedActionRow:
    tenant: str
    account_slug: str
    checkpoint_day: int
    mode: str
    signal: str | None
    motion_in: tuple[str, ...]
    evidence_must_include: tuple[str, ...]
    forbidden_motions: tuple[str, ...]
    notes: str


def load_expected_actions(
    tenant: str = "fleetops",
    *,
    gold_dir: Path | str = GOLD_DIR,
) -> tuple[ExpectedActionRow, ...]:
    """Load and validate ``<tenant>_expected_actions.json``. Fail-closed:
    an unknown mode, an unresolvable account slug, or a non-empty
    ``motion_in``/``signal`` on a ``mode: "none"`` row all raise
    :class:`ExpectedActionsGoldError`."""

    path = Path(gold_dir) / f"{tenant}_expected_actions.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ExpectedActionsGoldError(f"{path.name} must be a non-empty JSON array")
    rows = tuple(_row(item, tenant) for item in raw)
    if len(rows) < 18:
        raise ExpectedActionsGoldError(
            f"{path.name} has {len(rows)} rows, fewer than the 18-checkpoint coverage floor"
        )
    return rows


def _row(raw: Any, tenant: str) -> ExpectedActionRow:
    if not isinstance(raw, dict):
        raise ExpectedActionsGoldError("expected-actions row must be an object")
    if raw.get("tenant") != tenant:
        raise ExpectedActionsGoldError(f"row tenant {raw.get('tenant')!r} does not match {tenant!r}")
    account_slug = raw.get("account_slug")
    if not isinstance(account_slug, str) or not account_slug:
        raise ExpectedActionsGoldError("row missing account_slug")
    if account_slug not in _KNOWN_ACCOUNT_SLUGS:
        raise ExpectedActionsGoldError(f"unknown synthetic-book account slug: {account_slug}")

    mode = raw.get("mode")
    if mode not in GRADING_MODES:
        raise ExpectedActionsGoldError(f"unknown grading mode: {mode}")

    required = raw.get("required")
    if not isinstance(required, dict):
        raise ExpectedActionsGoldError("row missing required object")
    signal = required.get("signal")
    motion_in = tuple(required.get("motion_in", ()))
    evidence = tuple(required.get("evidence_must_include", ()))
    forbidden = tuple(raw.get("forbidden_motions", ()))

    for motion in (*motion_in, *forbidden):
        if motion not in PLAYBOOK_MOTIONS:
            raise ExpectedActionsGoldError(f"unknown motion in row for {account_slug}: {motion}")

    if mode == "none":
        if signal is not None or motion_in:
            raise ExpectedActionsGoldError(
                f"mode 'none' row for {account_slug} must have signal=null and empty motion_in"
            )
    else:
        if not motion_in:
            raise ExpectedActionsGoldError(
                f"mode {mode!r} row for {account_slug} must have a non-empty motion_in"
            )

    checkpoint_day = raw.get("checkpoint_day")
    if not isinstance(checkpoint_day, int):
        raise ExpectedActionsGoldError(f"row for {account_slug} missing integer checkpoint_day")

    return ExpectedActionRow(
        tenant=tenant,
        account_slug=account_slug,
        checkpoint_day=checkpoint_day,
        mode=mode,
        signal=signal,
        motion_in=motion_in,
        evidence_must_include=evidence,
        forbidden_motions=forbidden,
        notes=raw.get("notes", ""),
    )
