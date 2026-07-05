"""Judge-scored ablation: does wiring the golden corpus into Slot B's
``org_context`` actually improve drafted output, or just add tokens?

Same fixture request set, run twice per item: once with the corpus-blind
context (`OrgPack.slot_b_context()`, no disposition -- the exact context
every call site produced before this dispatch) and once with the
disposition-aware context (`slot_b_context(disposition=..., recommended_action=...)`,
now the live path's default -- see sweep.py) that additionally fences up to
two golden exemplars. Both sides are drafted with the LIVE Anthropic writer
and judge-scored N=3 per item on the judge's existing dimensions.

This is a TASTE-routed measurement (see dispatch routing table): the judge
itself is not yet validated against human labels (kappa pending an owner
labeling session), so every delta here is directional evidence, not proof.
`claim_boundary` says so on the artifact; do not read this as a quality gate.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_csm import QUALITY_DIMENSIONS
from eval.judge_nrun import aggregate
from ultra_csm.agent1.slot_b import (
    AnthropicReasonDraftWriter,
    ReasonDraftRequest,
    SLOT_B_PROMPT_VERSION,
    SlotBEvidence,
    SlotBPriority,
    SlotBPriorityFactor,
)
from ultra_csm.knowledge import load_org_pack

ARTIFACT_PATH = Path(__file__).with_name("org_pack_ablation.json")
SCHEMA_VERSION = 1
DEFAULT_RUNS_PER_ITEM = 3
AS_OF = "2026-06-27"

# Same fixture request set for both arms -- only org_context varies. One item
# carries disposition="escalate" (the only disposition with an unambiguous
# golden-corpus kind per knowledge.py's _DISPOSITION_EXEMPLAR_KIND); the other
# two exercise the recap_email default, matching how most live dispositions
# resolve today (see PROGRESS.md IF/THEN: only escalate is unambiguous).
_ITEMS = (
    {
        "candidate_id": "ablation-acme-escalate",
        "account_name": "Acme Logistics",
        "disposition": "escalate",
        "recommended_action": "recommend_next_best_action",
        "customer_contact_allowed": False,
        "score": 95,
        "factors": (
            SlotBPriorityFactor("milestones_overdue", 2.0, 50),
            SlotBPriorityFactor("health_red", 1.0, 30),
        ),
        "evidence": (
            SlotBEvidence("telemetry", "sig-acme-activation", "daily_active_assets", "2026-06-20T00:00:00Z"),
            SlotBEvidence("cs_platform", "cta-acme-overdue", "due_date", "2026-06-24"),
        ),
    },
    {
        "candidate_id": "ablation-globex-propose",
        "account_name": "Globex Manufacturing",
        "disposition": "propose_customer_action",
        "recommended_action": "draft_customer_outreach",
        "customer_contact_allowed": True,
        "score": 82,
        "factors": (
            SlotBPriorityFactor("adoption_drop", 0.34, 45),
            SlotBPriorityFactor("open_success_plan_gap", 1.0, 22),
        ),
        "evidence": (
            SlotBEvidence("telemetry", "sig-globex-drop", "weekly_active_users", "2026-06-21T00:00:00Z"),
            SlotBEvidence("cs_platform", "plan-globex-gap", "missing_owner", "2026-06-22"),
        ),
    },
    {
        "candidate_id": "ablation-initech-internal",
        "account_name": "Initech Finance",
        "disposition": "internal_review",
        "recommended_action": "recommend_next_best_action",
        "customer_contact_allowed": False,
        "score": 74,
        "factors": (
            SlotBPriorityFactor("milestone_due_soon", 1.0, 25),
            SlotBPriorityFactor("case_age_days", 9.0, 20),
        ),
        "evidence": (
            SlotBEvidence("cs_platform", "milestone-initech-training", "target_date", "2026-06-29"),
            SlotBEvidence("crm", "case-initech-42", "age_days", "2026-06-18"),
        ),
    },
)


def _build_request(item: dict, *, org_context: dict) -> ReasonDraftRequest:
    contact_allowed = item["customer_contact_allowed"]
    return ReasonDraftRequest(
        tenant_id="ablation-fixture-tenant",
        account_id=item["candidate_id"],
        account_name=item["account_name"],
        disposition=item["disposition"],
        recommended_action=item["recommended_action"],
        customer_contact_allowed=contact_allowed,
        priority=SlotBPriority(score=item["score"], factors=item["factors"]),
        evidence=item["evidence"],
        as_of=AS_OF,
        contact_name="Jordan Lee" if contact_allowed else None,
        contact_email="jordan@example.test" if contact_allowed else None,
        untrusted_text_fragments=(),
        org_context=org_context,
    )


def _request_dict(request: ReasonDraftRequest) -> dict:
    data = asdict(request)
    data["prompt_version"] = SLOT_B_PROMPT_VERSION
    return data


def _output_dict(output) -> dict:
    data = asdict(output)
    data["cited_evidence_ids"] = list(output.cited_evidence_ids)
    return data


def _mean_deltas(with_scores: list[dict], without_scores: list[dict]) -> dict[str, float]:
    deltas = {}
    for dim in QUALITY_DIMENSIONS:
        deltas[dim] = round(
            statistics.mean(w[dim] - wo[dim] for w, wo in zip(with_scores, without_scores)), 3
        )
    return deltas


def build_ablation_artifact(
    *,
    runs_per_item: int = DEFAULT_RUNS_PER_ITEM,
    writer: AnthropicReasonDraftWriter | None = None,
    judge: AnthropicQualityJudge | None = None,
) -> dict:
    pack = load_org_pack()
    writer = writer or AnthropicReasonDraftWriter()
    judge = judge or AnthropicQualityJudge(reasoning=True)

    results = []
    for item in _ITEMS:
        without_context = pack.slot_b_context()  # pre-dispatch behavior: no exemplars
        with_context = pack.slot_b_context(
            disposition=item["disposition"], recommended_action=item["recommended_action"]
        )
        has_exemplars = "golden_exemplars" in with_context
        without_request = _build_request(item, org_context=without_context)
        with_request = _build_request(item, org_context=with_context)

        without_output = writer.write(without_request)
        with_output = writer.write(with_request)

        without_vectors = [
            judge.score_output(_request_dict(without_request), _output_dict(without_output))
            for _ in range(runs_per_item)
        ]
        with_vectors = [
            judge.score_output(_request_dict(with_request), _output_dict(with_output))
            for _ in range(runs_per_item)
        ]
        without_agg = aggregate(without_vectors)
        with_agg = aggregate(with_vectors)

        results.append({
            "candidate_id": item["candidate_id"],
            "disposition": item["disposition"],
            "has_golden_exemplars": has_exemplars,
            "exemplar_kinds": (
                [e["kind"] for e in with_context.get("golden_exemplars", [])]
            ),
            "without_corpus": {
                "request": _request_dict(without_request),
                "output": _output_dict(without_output),
                "runs": without_vectors,
                "agg": without_agg,
            },
            "with_corpus": {
                "request": _request_dict(with_request),
                "output": _output_dict(with_output),
                "runs": with_vectors,
                "agg": with_agg,
            },
            "per_dimension_delta_with_minus_without": _mean_deltas(
                with_vectors, without_vectors
            ),
        })

    artifact = {
        "artifact": "org_pack_ablation",
        "schema_version": SCHEMA_VERSION,
        "generated_by": "eval.org_pack_ablation",
        "as_of": AS_OF,
        "draft_model_id": writer.model_id,
        "judge_model_id": judge.model_id,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_reasoning": judge.reasoning,
        "runs_per_item": runs_per_item,
        "n_items": len(_ITEMS),
        "results": results,
        "claim_boundary": (
            "judge not human-validated (kappa pending owner labels); deltas are "
            "directional, not proof"
        ),
    }
    return artifact


def write_ablation_artifact(
    output_path: Path = ARTIFACT_PATH,
    *,
    runs_per_item: int = DEFAULT_RUNS_PER_ITEM,
) -> dict:
    artifact = build_ablation_artifact(runs_per_item=runs_per_item)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_ITEM)
    parser.add_argument("--output", default=str(ARTIFACT_PATH))
    args = parser.parse_args(argv)

    artifact = write_ablation_artifact(Path(args.output), runs_per_item=args.runs)
    for result in artifact["results"]:
        print(
            f"{result['candidate_id']:28} exemplars={result['exemplar_kinds']} "
            f"delta={result['per_dimension_delta_with_minus_without']}"
        )
    print(f"artifact -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
