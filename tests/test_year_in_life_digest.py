"""Year-in-the-life digest demo artifact."""

from __future__ import annotations

from eval.year_in_life_digest import build_year_in_life_digest


def test_year_in_life_digest_fixture_mode_writes_demo_artifact(tmp_path):
    output = tmp_path / "digest.json"

    artifact = build_year_in_life_digest(
        output_path=output,
        days=(0, 30),
        top_n=1,
        live=False,
        max_cost_usd=1.0,
    )

    assert output.exists()
    assert artifact["claim_boundary"]["simulation"] is True
    assert artifact["claim_boundary"]["live_tenant"] is False
    assert artifact["claim_boundary"]["contains_full_synthetic_drafts"] is True
    assert artifact["claim_boundary"]["deterministic_spine_verified"] is True
    assert artifact["config"]["live"] is False
    assert len(artifact["snapshots"]) == 2
    for snapshot in artifact["snapshots"]:
        assert snapshot["deterministic_spine_hash"]
        assert len(snapshot["selected_accounts"]) == 1
        selected = snapshot["selected_accounts"][0]
        assert selected["draft_mode"] == "fixture"
        assert selected["customer_draft"]
        assert selected["reason"]
