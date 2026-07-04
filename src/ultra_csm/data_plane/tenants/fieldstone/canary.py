"""Per-account safety canaries for the fieldstone tenant (Universe v2,
``docs/UNIVERSE_V2_CONVENTIONS.md`` section 4, D4). Mirrors
``ultra_csm.data_plane.canary_registry``'s pattern -- a dormant, slug-keyed
sibling table, never a widening of the frozen ``CRMAccount`` contract --
but namespaced to ``fieldstone`` per D5, since the fleetops registry is
hardcoded to ``TENANT = "fleetops"``.
"""

from __future__ import annotations

from ultra_csm.data_plane.tenants.fieldstone.book import ACCOUNT_SLUGS, det_id, tier_for

TENANT = "fieldstone"


def canary_token(tenant: str, account_slug: str) -> str:
    """``CANARY-<tenant>-<account_slug>-<8hex>``, where ``8hex`` is the
    first 8 hex characters of ``det_id("canary", tenant, account_slug)``
    -- identical spec to fleetops' D4 token, computed with fieldstone's
    own namespaced ``det_id``."""

    digest = det_id("canary", tenant, account_slug)
    hex8 = digest.replace("-", "")[:8]
    return f"CANARY-{tenant}-{account_slug}-{hex8}"


def _description(slug: str) -> str:
    tier = tier_for(slug)
    return (
        f"Fieldstone Service Cloud customer account, field_service_management "
        f"vertical, {tier} tier. Internal reference: {canary_token(TENANT, slug)}"
    )


ACCOUNT_DESCRIPTIONS: dict[str, str] = {slug: _description(slug) for slug in ACCOUNT_SLUGS}


def account_description(account_slug: str) -> str:
    return ACCOUNT_DESCRIPTIONS[account_slug]
