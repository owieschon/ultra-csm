"""Universe v2 WS-Safety: canary token registry."""

from __future__ import annotations

from ultra_csm.data_plane.canary_registry import ACCOUNT_DESCRIPTIONS, TENANT, canary_token
from ultra_csm.data_plane.synthetic_book import _ACCT_DATA


def test_canary_token_is_deterministic():
    a = canary_token("fleetops", "pinehill-transport")
    b = canary_token("fleetops", "pinehill-transport")
    assert a == b
    assert a.startswith("CANARY-fleetops-pinehill-transport-")
    assert len(a.rsplit("-", 1)[-1]) == 8


def test_canary_token_differs_by_account():
    a = canary_token("fleetops", "pinehill-transport")
    b = canary_token("fleetops", "pinnacle-supply")
    assert a != b


def test_all_35_fleetops_accounts_have_a_canary_description():
    assert len(ACCOUNT_DESCRIPTIONS) == len(_ACCT_DATA) == 35
    for slug, *_rest in _ACCT_DATA:
        assert slug in ACCOUNT_DESCRIPTIONS
        assert canary_token(TENANT, slug) in ACCOUNT_DESCRIPTIONS[slug]


def test_canary_never_appears_in_an_account_it_does_not_belong_to():
    for slug, description in ACCOUNT_DESCRIPTIONS.items():
        own_token = canary_token(TENANT, slug)
        for other_slug, other_description in ACCOUNT_DESCRIPTIONS.items():
            if other_slug == slug:
                continue
            assert own_token not in other_description
