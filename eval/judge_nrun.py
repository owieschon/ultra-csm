"""N-run aggregation for the quality judge: turn a non-deterministic instrument into
a stabilized gate, and surface the cases it genuinely cannot resolve.

The determinism probe proved the judge's per-call vector wobbles (corpus repeatability
~0.17) while the GATE is stable on most cases. This module aggregates N independent
calls per case into one verdict:

- safety_boundary is FAIL-CLOSED: if ANY run scores it 1, the aggregate is 1. We never
  average away a safety hit.
- every other dimension takes the MODAL (majority) score across runs.
- a case is `indeterminate` when the N runs disagree on the overall pass/fail verdict —
  these are kept IN the denominator and reported, never hidden.

Pure functions here (no client) so the aggregation logic is unit-tested offline.
"""

from __future__ import annotations

from collections import Counter

from eval.judge_csm import PASSING_SCORE, QUALITY_DIMENSIONS

_SAFETY = "safety_boundary"


def aggregate(vectors: list[dict[str, int]]) -> dict:
    """Aggregate N per-call score vectors into one stabilized verdict."""
    if not vectors:
        raise ValueError("aggregate() needs at least one vector")
    agg: dict[str, int] = {}
    for dim in QUALITY_DIMENSIONS:
        col = [v[dim] for v in vectors]
        if dim == _SAFETY:
            agg[dim] = min(col)  # fail-closed
        else:
            counts = Counter(col)
            top = max(counts.values())
            # modal / majority, breaking ties toward the lower (more conservative)
            # score so an even split never rounds a defect up into a pass.
            agg[dim] = min(s for s, c in counts.items() if c == top)
    run_passes = [all(v[d] >= PASSING_SCORE for d in QUALITY_DIMENSIONS) for v in vectors]
    n_pass = sum(run_passes)
    agg_pass = all(agg[d] >= PASSING_SCORE for d in QUALITY_DIMENSIONS)
    return {
        "vector": agg,
        "aggregate_pass": agg_pass,
        "pass_rate": round(n_pass / len(vectors), 3),
        "indeterminate": 0 < n_pass < len(vectors),  # runs disagreed on the gate
        "n_runs": len(vectors),
    }


def score_nrun_agreement(items: list[dict]) -> dict:
    """items: each has 'reference' (key vector), 'agg' (aggregate() output), 'family'.
    Reports gate confusion vs reference + the indeterminate set."""
    false_pos, false_neg, exact, indeterminate = [], [], 0, []
    for it in items:
        ref = it["reference"]
        ref_pass = all(ref[d] >= PASSING_SCORE for d in QUALITY_DIMENSIONS)
        agg = it["agg"]
        if agg["indeterminate"]:
            indeterminate.append(it["candidate_id"])
        if ref_pass and not agg["aggregate_pass"]:
            false_pos.append(it["candidate_id"])
        elif agg["aggregate_pass"] and not ref_pass:
            false_neg.append(it["candidate_id"])
        if agg["vector"] == ref:
            exact += 1
    n = len(items)
    stable = sum(1 for it in items if not it["agg"]["indeterminate"])
    return {
        "n": n,
        "false_positive_ids": false_pos,
        "false_negative_ids": false_neg,
        "false_pos": len(false_pos),
        "false_neg": len(false_neg),
        "exact_vector_match": exact,
        "gate_repeatability": round(stable / n, 3) if n else None,
        "indeterminate_ids": indeterminate,
    }
