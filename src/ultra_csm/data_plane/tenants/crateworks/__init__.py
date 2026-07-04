"""Crateworks WMS tenant (Universe v2, Wave 3, WS-Tenant-Crateworks).

The HYGIENE tenant: messy, homegrown-CRM data at whole-tenant scale. See
``docs/TENANT_CRATEWORKS_BIBLE.md`` for canon and ``docs/UNIVERSE_V2_CONVENTIONS.md``
section 1 for the tenant-canon row. Fixture + fake-transport only (no live
seeding) per CONVENTIONS' live/fixture boundary.
"""

from __future__ import annotations

from ultra_csm.data_plane.tenants.crateworks.book import (
    ACCOUNTS,
    CONTROL_SLUGS,
    DOCKSIDE_SLUG,
    FlatCrateworksBook,
    build_flat_crateworks_book,
    build_crateworks_data_plane,
    crateworks_account_id,
)
from ultra_csm.data_plane.tenants.crateworks.comms import (
    FakeZendeskClient,
    arc_c1_cases,
    arc_c1_comms,
    arc_c1_relationships,
    dockside_ticket,
)

__all__ = [
    "ACCOUNTS",
    "CONTROL_SLUGS",
    "DOCKSIDE_SLUG",
    "FlatCrateworksBook",
    "build_flat_crateworks_book",
    "build_crateworks_data_plane",
    "crateworks_account_id",
    "FakeZendeskClient",
    "arc_c1_cases",
    "arc_c1_comms",
    "arc_c1_relationships",
    "dockside_ticket",
]
