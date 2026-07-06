"""Bounded live verification of the reconciliation agent (Harvest 31 /
report 52). Manual invocation only -- no scheduler, no standing job (same
posture as judge_live_csm.py). Requires ANTHROPIC_API_KEY.

Sample: ONE account (pinnacle-supply, as_of=2026-06-25) -- the account
Phase 0's survey confirmed fires real, evidence-backed factors across all
three lenses (value_model divergences + risk lens + expansion lens). Not
every fixture account in the book was checked; this is a deliberately
small, explicitly-stated sample under the dispatch's $25 live-verification
ceiling, not a claim of book-wide coverage.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.reconciliation_judge import (
    AnthropicReconciliationJudge,
    RECONCILIATION_JUDGE_PROMPT_VERSION,
    passes,
)
from ultra_csm.data_plane import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
    account_id_for,
)
from ultra_csm.data_plane.synthetic_book import build_synthetic_book
from ultra_csm.reconciliation_agent import (
    RECONCILIATION_PROMPT_VERSION,
    AnthropicReconciliationWriter,
    _raw_evidence_pool,
    explain,
)

ARTIFACT_DIR = Path(__file__).with_name("gold")
DEFAULT_OUTPUT = ARTIFACT_DIR / "reconciliation_battery.json"
DEFAULT_ACCOUNT_SLUG = "pinnacle-supply"
DEFAULT_AS_OF = "2026-06-25"


def _data_plane() -> CustomerDataPlane:
    book = build_synthetic_book()
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(data=book),
        cs=FixtureCSPlatformConnector(data=book),
        telemetry=FixtureProductTelemetryConnector(data=book),
    )


def _evidence_dict(ref) -> dict:
    return {"source": ref.source, "source_id": ref.source_id, "field": ref.field, "observed_at": ref.observed_at}


def run_verification(
    *, account_slug: str = DEFAULT_ACCOUNT_SLUG, as_of: str = DEFAULT_AS_OF,
) -> dict[str, Any]:
    account_id = account_id_for(account_slug)
    dp = _data_plane()

    writer = AnthropicReconciliationWriter()
    result = explain(dp, account_id, as_of=as_of, writer=writer)
    if result is None:
        raise SystemExit(f"account {account_slug!r} has no CS data at as_of={as_of}")

    judge = AnthropicReconciliationJudge()
    raw_evidence = _raw_evidence_pool(dp, account_id, as_of=as_of)
    explanation_scores, candidate_scores = judge.score(
        deterministic_signals=[
            {
                "name": s.name, "value": s.value, "contribution": s.contribution,
                "surfaced_by_lenses": list(s.surfaced_by_lenses),
                "evidence": [_evidence_dict(e) for e in s.evidence],
            }
            for s in result.deterministic_signals
        ],
        raw_evidence=[_evidence_dict(e) for e in raw_evidence],
        explanation=result.explanation.text,
        candidates=[
            {"claim": c.claim, "confidence": c.confidence, "evidence": [_evidence_dict(e) for e in c.evidence]}
            for c in result.candidate_divergences
        ],
    )

    kept_candidates = []
    dropped_count = 0
    for candidate, scores in zip(result.candidate_divergences, candidate_scores, strict=True):
        if passes(scores):
            kept_candidates.append({**asdict(candidate), "judge_scores": scores})
        else:
            dropped_count += 1

    artifact = {
        "artifact": "reconciliation_battery",
        "account_id": account_id,
        "account_slug": account_slug,
        "as_of": as_of,
        "reconciliation_prompt_version": RECONCILIATION_PROMPT_VERSION,
        "judge_prompt_version": RECONCILIATION_JUDGE_PROMPT_VERSION,
        "deterministic_signal_count": len(result.deterministic_signals),
        "explanation": {
            "text": result.explanation.text,
            "disclaimer": result.explanation.disclaimer,
            "judge_scores": explanation_scores,
        },
        "candidate_divergences_proposed": len(result.candidate_divergences),
        "candidate_divergences_kept": kept_candidates,
        "candidate_divergences_dropped_by_judge": dropped_count,
        "hard_ok": passes(explanation_scores) and (
            len(result.candidate_divergences) == 0 or len(kept_candidates) > 0 or dropped_count == len(result.candidate_divergences)
        ),
    }
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--account", default=DEFAULT_ACCOUNT_SLUG)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    args = parser.parse_args(argv)

    artifact = run_verification(account_slug=args.account, as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Reconciliation battery ({args.account}): "
        f"explanation_scores={artifact['explanation']['judge_scores']} "
        f"candidates_proposed={artifact['candidate_divergences_proposed']} "
        f"candidates_kept={len(artifact['candidate_divergences_kept'])} "
        f"hard_ok={artifact['hard_ok']}"
    )
    print(f"artifact -> {args.output}")
    return 0 if artifact["hard_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
