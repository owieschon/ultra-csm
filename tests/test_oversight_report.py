"""Oversight evidence pack: render-only, deterministic, honest about gaps."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.oversight_report import (
    DISCLAIMER,
    build_oversight_report,
    render_markdown,
    write_oversight_report,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "oversight_report.py"


def test_report_is_deterministic_byte_identical(tmp_path):
    first = write_oversight_report(
        json_out=tmp_path / "a.json", md_out=tmp_path / "a.md"
    )
    second = write_oversight_report(
        json_out=tmp_path / "b.json", md_out=tmp_path / "b.md"
    )

    assert first == second
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert (tmp_path / "a.md").read_bytes() == (tmp_path / "b.md").read_bytes()


def test_disclaimer_heads_both_outputs(tmp_path):
    report = write_oversight_report(
        json_out=tmp_path / "r.json", md_out=tmp_path / "r.md"
    )

    assert report["disclaimer"] == DISCLAIMER
    assert "not a compliance assessment" in DISCLAIMER
    md = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert DISCLAIMER in md.splitlines()[2]
    assert DISCLAIMER in (tmp_path / "r.json").read_text(encoding="utf-8")


def test_not_instrumented_section_present_and_honest():
    report = build_oversight_report()
    gaps = report["sections"]["8_not_instrumented"]

    assert len(gaps) >= 5
    joined = " ".join(gaps)
    assert "separation-of-duties" in joined.lower() or "separation of duties" in joined.lower()
    assert "SLA" in joined


def test_claims_carry_ledger_row_refs():
    report = build_oversight_report()
    md = render_markdown(report)

    events = report["sections"]["1_human_oversight_events"]["verdict_events"]
    assert events, "verdict ledger must load"
    # every verdict event's proposal_id is quoted inline in the markdown
    for event in events:
        assert f"`{event['proposal_id']}`" in md
    receipts = report["sections"]["1_human_oversight_events"]["committed_outbound_receipts"]
    for receipt in receipts:
        assert f"`{receipt['receipt_id']}`" in md
        assert f"`{receipt['payload_sha256']}`" in md


def test_sections_map_to_lane_spec():
    report = build_oversight_report()
    assert sorted(report["sections"]) == [
        "1_human_oversight_events",
        "2_separation_of_duties",
        "3_authority_boundaries",
        "4_suppression_and_release",
        "5_degradation_honesty",
        "6_quality_measurement",
        "7_autonomy_provenance",
        "8_not_instrumented",
    ]
    # quality section quotes the evidence artifacts rather than restating numbers
    quality = report["sections"]["6_quality_measurement"]
    assert quality["judge_validation"] is not None
    assert quality["judge_agreement_quoted"]["judge_prompt_version"]


def test_module_has_no_write_path_to_gate_or_ledgers(tmp_path):
    # Foil 1: static — the module must not import any gate/DB mutation surface.
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    forbidden = ("gate", "authorizer.authorize", "psycopg", "db", "outbound", "quality_breaker")
    for name in imported:
        for bad in ("governance.gate", "psycopg", "agent1.outbound", "ultra_csm.db"):
            assert bad not in name, f"render-only module imports write surface: {name}"
    assert forbidden  # documents intent

    # Foil 2: behavioral — rendering must not modify any source ledger it reads.
    ledger_paths = [
        Path(__file__).resolve().parents[1] / rel
        for rel in (
            "eval/autonomy_verdict_ledger.jsonl",
            "demo_state/commit_audit.jsonl",
            "demo_state/quality_breaker/operator_events.jsonl",
        )
        if (Path(__file__).resolve().parents[1] / rel).exists()
    ]
    before = {p: p.read_bytes() for p in ledger_paths}
    write_oversight_report(json_out=tmp_path / "x.json", md_out=tmp_path / "x.md")
    for p, content in before.items():
        assert p.read_bytes() == content, f"renderer mutated ledger {p}"
