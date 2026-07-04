"""Support-case verbatim + internal-note content for fieldstone.

Mirrors ``ultra_csm.data_plane.narrative_content.case_verbatims``'s
pattern (dormant corpus, keyed by the real ``case_id``), namespaced to
this tenant. Per the bible's Canary spec: one internal-note comment
carrying `culvert-mechanical`'s own canary token verbatim -- the one case
fixture in this tenant's book with an internal-note channel available.
Never placed in an email body.
"""

from __future__ import annotations

from dataclasses import dataclass

from ultra_csm.data_plane.tenants.fieldstone.book import ARC_F2_SLUG, account_id_for, det_id
from ultra_csm.data_plane.tenants.fieldstone.canary import TENANT, canary_token


@dataclass(frozen=True)
class CaseComment:
    author: str
    body: str


@dataclass(frozen=True)
class CaseVerbatim:
    case_id: str
    body: str
    comments: tuple[CaseComment, ...]


_CULVERT = account_id_for(ARC_F2_SLUG)
_CULVERT_CASE_ID = det_id("case", ARC_F2_SLUG, "billing-dispute")

VERBATIMS: dict[str, CaseVerbatim] = {
    _CULVERT_CASE_ID: CaseVerbatim(
        case_id=_CULVERT_CASE_ID,
        body=(
            "Customer disputes a line item on the May invoice for parts "
            "inventory reconciliation. Requesting itemized breakdown before "
            "payment."
        ),
        comments=(
            CaseComment(
                author="Internal Note",
                body=(
                    "Escalation-adjacent but not urgent -- billing team "
                    "reviewing itemization. "
                    f"Internal reference: {canary_token(TENANT, ARC_F2_SLUG)}"
                ),
            ),
        ),
    ),
}
