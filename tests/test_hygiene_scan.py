"""Hygiene scan for active CSM-facing surfaces."""

from __future__ import annotations

from scripts.hygiene_scan import scan


def test_active_csm_surface_has_no_source_or_wrong_domain_residue():
    assert scan() == []


def test_hygiene_scan_catches_new_product_surface_residue(tmp_path):
    probe = tmp_path / "src" / "ultra_csm" / "agents" / "_probe.py"
    probe.parent.mkdir(parents=True)
    bad_words = " ".join(
        ["fulfill" + "ment", "ship" + "_date", "S" + "KU", "Cod" + "ex"]
    )
    probe.write_text(f'BAD = "{bad_words}"\n')

    findings = scan(("src",), root=tmp_path)

    expected = {
        ("wrong-domain", "fulfill" + "ment"),
        ("wrong-domain", "ship" + "_date"),
        ("wrong-domain", "s" + "ku"),
        ("meta-residue", "cod" + "ex"),
    }
    assert {(f.kind, f.match.lower()) for f in findings} >= expected


def test_hygiene_scan_rejects_legacy_paths(tmp_path):
    legacy = tmp_path / "eval" / "_old" / ("fulfill" + "ment") / "engine.py"
    legacy.parent.mkdir(parents=True)
    legacy_words = " ".join(["fulfill" + "ment", "ship" + "_date", "S" + "KU"])
    legacy.write_text(f'OK = "{legacy_words}"\n')

    assert scan(("eval",), root=tmp_path)


def test_hygiene_scan_rejects_backstage_delivery_ceremony(tmp_path):
    probe = tmp_path / "docs" / "_probe.md"
    probe.parent.mkdir(parents=True)
    backstage_phrases = " | ".join(
        (
            "live " + "application",
            "target-" + "company brief",
            "publication " + "window",
        )
    )
    probe.write_text(backstage_phrases + "\n")

    findings = scan(("docs",), root=tmp_path)

    expected = {
        "live " + "application",
        "target-" + "company brief",
        "publication " + "window",
    }
    assert {f.match.lower() for f in findings if f.kind == "meta-residue"} == expected
