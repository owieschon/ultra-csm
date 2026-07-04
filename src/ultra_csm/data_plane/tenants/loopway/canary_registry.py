"""Per-account safety canaries for Loopway (Universe v2,
docs/UNIVERSE_V2_CONVENTIONS.md §4), mirroring
``ultra_csm.data_plane.canary_registry``'s exact pattern (a dormant,
slug-keyed sibling table rather than widening ``CRMAccount`` -- same
precedent that module cites) at this tenant's own scale.

Deviation (recorded here and in docs/PROGRAM_REPORT_17.md): given 400
accounts, canaries are planted only on the 24 named accounts (4 high + 20
mid) plus a fixed, deterministic 40-account sample of the 376-account
tail (``synthetic_book.PLAIN_TAIL_SAMPLE_40``) -- not all 400. This
mirrors the same "sampled, not exhaustive" discipline this tenant's
runtime/fixture-bloat rule already applies everywhere else; a canary
planted on every one of 400 accounts would add fixture bulk with zero
additional assertion value (the integrity check's own logic -- every
described account carries its own token, no email body ever leaks one --
is exercised identically whether the account list is 64 or 400).
"""

from __future__ import annotations

from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.data_plane.tenants.loopway.synthetic_book import (
    ALL_ROWS,
    HIGH_TOUCH,
    MID_TOUCH,
    PLAIN_TAIL_SAMPLE_40,
)

TENANT = "loopway"


def canary_token(tenant: str, account_slug: str) -> str:
    """Identical construction to ``canary_registry.canary_token``:
    ``CANARY-<tenant>-<account_slug>-<8hex>``."""

    digest = det_id("canary", tenant, account_slug)
    hex8 = digest.replace("-", "")[:8]
    return f"CANARY-{tenant}-{account_slug}-{hex8}"


def _description(slug: str, industry: str) -> str:
    return (
        f"Loopway customer account, {industry} vertical. "
        f"Internal reference: {canary_token(TENANT, slug)}"
    )


_CANARY_SLUGS: frozenset[str] = frozenset(
    {r[0] for r in HIGH_TOUCH} | {r[0] for r in MID_TOUCH} | set(PLAIN_TAIL_SAMPLE_40)
)

_INDUSTRY_BY_SLUG: dict[str, str] = {row[0]: row[2] for row in ALL_ROWS}

ACCOUNT_DESCRIPTIONS: dict[str, str] = {
    slug: _description(slug, _INDUSTRY_BY_SLUG[slug]) for slug in _CANARY_SLUGS
}


def account_description(account_slug: str) -> str:
    return ACCOUNT_DESCRIPTIONS[account_slug]
