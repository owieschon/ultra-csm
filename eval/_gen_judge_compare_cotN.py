"""One-off: regenerate judge_compare.json with ONLY the cot@N arm.

compare_judges.py's default run scores both terse@N and cot@N (2x cost) for
its own terse-vs-cot comparison narrative. judge_validation_status() only
ever reads the cot@N arm (HARD_ARM = "cot@N" in judge_validation.py) for the
actual hard-layer gate. Report 31's job is the v7->v8 grounding-anchor fix,
not re-litigating that comparison, so this scopes the live spend to the arm
the gate actually needs -- a deliberate, disclosed cost cut (K2: additive,
smallest fork), not a silent one. terse@N is left as whatever the last
compare_judges.py run wrote (stale relative to this run) -- the report
states this plainly.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from eval.compare_judges import OUT_PATH
from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_nrun import aggregate, score_nrun_agreement
from eval.run_quality_judge import load_hard
from ultra_csm.cost_tracker import compute_cost

RUNS = 5
MAX_RETRIES = 5  # K7: transient parse/format hiccups, not a systemic bug
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 529}
USAGE_PATH = Path(".judge_compare_cotN_usage.json")
CHECKPOINT_PATH = Path(".judge_compare_cotN_checkpoint.json")


class _UsageRecordingClient:
    def __init__(self) -> None:
        from anthropic import Anthropic

        self._client = Anthropic()
        self.messages = self
        self.calls: list[dict] = []
        self._write_summary()

    def create(self, **kwargs):
        started = time.monotonic()
        msg = self._client.messages.create(**kwargs)
        elapsed_ms = (time.monotonic() - started) * 1000
        usage = getattr(msg, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        model_id = str(kwargs.get("model") or "unknown")
        self.calls.append(
            {
                "model_id": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": compute_cost(model_id, input_tokens, output_tokens),
                "latency_ms": elapsed_ms,
            }
        )
        self._write_summary()
        return msg

    def summary(self) -> dict:
        return {
            "calls": len(self.calls),
            "input_tokens": sum(call["input_tokens"] for call in self.calls),
            "output_tokens": sum(call["output_tokens"] for call in self.calls),
            "cost_usd": round(sum(call["cost_usd"] for call in self.calls), 6),
        }

    def _write_summary(self) -> None:
        USAGE_PATH.write_text(json.dumps(self.summary(), sort_keys=True) + "\n", encoding="utf-8")


def _score_with_retry(judge, request, output):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return judge.score_output(request, output)
        except Exception as exc:
            last_exc = exc
            if not _retryable(exc):
                break
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 30))
    raise last_exc


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        return True
    status_code = getattr(exc, "status_code", None)
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    return exc.__class__.__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "OverloadedError",
        "RateLimitError",
    }


def run_arm_retrying(judge, items: list[dict], n: int) -> dict:
    scored = _load_checkpoint()
    already_scored = {case["candidate_id"] for case in scored}
    total = len(items)
    for index, it in enumerate(items, start=1):
        if it["candidate_id"] in already_scored:
            print(f"scoring hard case {index}/{total} id={it['candidate_id']} checkpoint-hit", flush=True)
            continue
        print(f"scoring hard case {index}/{total} id={it['candidate_id']}", flush=True)
        vectors = [_score_with_retry(judge, it["request"], it["output"]) for _ in range(n)]
        scored.append({
            "candidate_id": it["candidate_id"],
            "family": it["family"],
            "reference": it["reference"],
            "agg": aggregate(vectors),
        })
        _write_checkpoint(scored)
    report = score_nrun_agreement(scored)
    report["cases"] = scored
    return report


def _load_checkpoint() -> list[dict]:
    if not CHECKPOINT_PATH.exists():
        return []
    payload = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("judge compare checkpoint cases must be a list")
    return cases


def _write_checkpoint(cases: list[dict]) -> None:
    CHECKPOINT_PATH.write_text(
        json.dumps({"cases": cases}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    items = load_hard()
    client = _UsageRecordingClient()
    judge = AnthropicQualityJudge(client=client, reasoning=True)
    judge._max_tokens = max(judge._max_tokens, 1400)
    cot_arm = run_arm_retrying(judge, items, RUNS)

    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else {}
    existing["model_id"] = judge.model_id
    existing["judge_prompt_version"] = JUDGE_PROMPT_VERSION
    existing["runs_per_case"] = RUNS
    existing.setdefault("arms", {})
    existing["arms"]["cot@N"] = cot_arm
    OUT_PATH.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"cot@N: n={cot_arm['n']} false_neg={cot_arm.get('false_neg')} false_pos={cot_arm.get('false_pos')}")
    print(f"usage: {client.summary()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
