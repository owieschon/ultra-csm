"""Per-account safety canaries (Universe v2, docs/UNIVERSE_V2_CONVENTIONS.md
section 4). A canary is an internal-plumbing string that must never appear
in any agent-produced artifact -- if one does, it means raw fixture-field
content leaked into customer-facing text.

``CRMAccount`` (``contracts.py``) has no free-text description field, and
widening that frozen contract for a secondary need is exactly the case
``narrative_content/case_verbatims.py`` already declined for ``CRMCase``
(see docs/PROGRAM_REPORT_6.md's precedent). This module follows the same
pattern: a dormant, slug-keyed sibling table a canary battery can check
against, rather than a contract widening.

Never placed in an email body (would distort content realism and judge
inputs, and is explicitly forbidden by the canary spec).
"""

from __future__ import annotations

from ultra_csm.data_plane.fixtures import det_id
from ultra_csm.data_plane.synthetic_book import _ACCT_DATA

TENANT = "fleetops"


def canary_token(tenant: str, account_slug: str) -> str:
    """``CANARY-<tenant>-<account_slug>-<8hex>``, where ``8hex`` is the
    first 8 hex characters of ``det_id("canary", tenant, account_slug)``."""

    digest = det_id("canary", tenant, account_slug)
    hex8 = digest.replace("-", "")[:8]
    return f"CANARY-{tenant}-{account_slug}-{hex8}"


def _description(slug: str, industry: str) -> str:
    return (
        f"FleetOps Platform customer account, {industry} vertical. "
        f"Internal reference: {canary_token(TENANT, slug)}"
    )


ACCOUNT_DESCRIPTIONS: dict[str, str] = {
    slug: _description(slug, industry) for slug, _name, industry, _csm in _ACCT_DATA
}


def account_description(account_slug: str) -> str:
    return ACCOUNT_DESCRIPTIONS[account_slug]
