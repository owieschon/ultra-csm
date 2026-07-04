"""Lazy/cached base-book accessor for Loopway, mirroring
``ultra_csm.data_plane.narrative_shared.base_synthetic_book`` -- compute
the 400-account book once and cache it; every battery/eval imports this
instead of calling ``build_synthetic_book()`` directly, so a 90-second
runtime ceiling isn't spent rebuilding the same 400-account book on every
call within one process (mandatory per this workstream's runtime
discipline -- see ``docs/TENANT_LOOPWAY_BIBLE.md``'s "Runtime + sampling
discipline" section).
"""

from __future__ import annotations

from ultra_csm.data_plane.fixtures import FixtureCustomerData
from ultra_csm.data_plane.tenants.loopway.synthetic_book import build_synthetic_book

_BASE_BOOK: FixtureCustomerData | None = None


def base_synthetic_book() -> FixtureCustomerData:
    global _BASE_BOOK
    if _BASE_BOOK is None:
        _BASE_BOOK = build_synthetic_book()
    return _BASE_BOOK
