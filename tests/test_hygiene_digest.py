"""Phase 5 (MP-W1R, D7): normalized-token digest denylist in hygiene_scan.py.

This test file must NEVER contain the real denylisted term -- it proves the
MECHANISM with a synthetic term and a TEST-ONLY denylist parameter, per the
dispatch's own D7 rule. A preimage for the production digest cannot and
must not be constructed to "verify" it directly.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hygiene_scan  # noqa: E402


_SYNTHETIC_TERM = "zorblequax"  # a made-up word, not a real company name
_TEST_DENYLIST = (hashlib.sha256(_SYNTHETIC_TERM.encode("utf-8")).hexdigest(),)


def test_digest_mechanism_catches_a_planted_synthetic_term_in_any_form():
    assert hygiene_scan._digest_hit_count("the zorble quax rollout", _TEST_DENYLIST) == 1
    assert hygiene_scan._digest_hit_count("a Zorble-Quax pilot", _TEST_DENYLIST) == 1
    assert hygiene_scan._digest_hit_count("ZorbleQuax Inc.", _TEST_DENYLIST) == 1


def test_digest_mechanism_clean_pass_on_unrelated_text():
    assert hygiene_scan._digest_hit_count("this text discusses ultra csm eval batteries", _TEST_DENYLIST) == 0
    # The real production denylist must also stay silent on ordinary text.
    assert hygiene_scan._digest_hit_count("this text discusses ultra csm eval batteries") == 0


def test_single_token_digest_does_not_join_adjacent_short_variables():
    synthetic = hashlib.sha256("xy".encode("utf-8")).hexdigest()
    original = hygiene_scan.SINGLE_TOKEN_DIGEST_DENYLIST
    hygiene_scan.SINGLE_TOKEN_DIGEST_DENYLIST = (synthetic,)
    try:
        assert hygiene_scan._digest_hit_count("xy", ()) == 1
        assert hygiene_scan._digest_hit_count("x, y", ()) == 0
    finally:
        hygiene_scan.SINGLE_TOKEN_DIGEST_DENYLIST = original


def test_digest_finding_never_surfaces_the_matched_text():
    fixture = Path("/tmp/_w1r_digest_test_fixture.py")
    fixture.write_text("# a zorble quax reference\n", encoding="utf-8")
    try:
        original = hygiene_scan.DIGEST_DENYLIST
        hygiene_scan.DIGEST_DENYLIST = _TEST_DENYLIST
        try:
            findings = hygiene_scan._raw_scan((str(fixture),), root=fixture.parent)
        finally:
            hygiene_scan.DIGEST_DENYLIST = original
    finally:
        fixture.unlink(missing_ok=True)

    digest_findings = [f for f in findings if f.kind == "digest-residue"]
    assert len(digest_findings) == 1
    assert digest_findings[0].match == "[redacted]"
    assert _SYNTHETIC_TERM not in digest_findings[0].match
