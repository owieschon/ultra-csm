from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from eval.external_corpus_probe import run_external_corpus_probe

API_KEY_ENV = "CORPUS_A_" "API_KEY"


def test_external_corpus_probe_writes_runtime_outputs_outside_repo(
    tmp_path,
    monkeypatch,
):
    def fake_run(cmd, **kwargs):  # noqa: ANN001 - subprocess.run-shaped test double
        del kwargs
        header_path = Path(cmd[cmd.index("--dump-header") + 1])
        header_path.write_text("HTTP/2 206\r\nContent-Range: 0-1/2\r\n", encoding="utf-8")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [
                    {"id": "acct-001", "name": "Alpha"},
                    {"id": "acct-002", "name": "Beta"},
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr("eval.external_corpus_probe.subprocess.run", fake_run)

    summary = run_external_corpus_probe(
        output_root=tmp_path,
        limit=2,
        page_size=2,
        run_label="unit",
        env={
            "CORPUS_A_BASE_URL": "https://example.invalid/rest/v1",
            "CORPUS_A_TABLE": "records",
            API_KEY_ENV: "test-key",
        },
    )

    assert summary["relay_fidelity"] == {
        "rows_fetched": 2,
        "source_reported_count": 2,
        "fetched_all_reported_rows": True,
        "probe_limit": 2,
        "pages": 1,
    }
    assert summary["mapping"]["confirmations_loaded"] is False
    assert summary["mapping"]["silent_guess_count"] == 0
    assert summary["ingest"]["records_typed"] == {
        "CRMAccount": 0,
        "CRMContact": 0,
        "CRMOpportunity": 0,
    }
    assert summary["scoring_readiness"] == {
        "typed_crm_accounts": 0,
        "work_item_scorer_ran": False,
        "scoreable_accounts": 0,
        "reason": (
            "CRM-only ingest lacks CS-platform health, onboarding, outcome, "
            "and product-telemetry rails; work-item scoring would be hollow."
        ),
    }
    assert (tmp_path / "unit" / "raw_records.json").exists()
    assert (tmp_path / "unit" / "mapping_proposal.json").exists()
    assert (tmp_path / "unit" / "sanitized_summary.json").exists()
