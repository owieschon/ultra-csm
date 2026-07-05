"""Judge-on-live: manually-invoked N-run judge scoring of Slot B drafts for
a real story day, per this dispatch's Decisions section.

Reads the frozen anchor (~/ultra-csm-corpus-runs/live-reseed-20260704/anchor.json)
for the current `anchor_day` (day-offset from the narrative's SEED_DATE,
2026-06-21 -- see data_plane/synthetic_book.py). There is no existing
operating-artifact snapshot of that day's generated drafts in this repo (no
daily work-queue keyed by anchor day exists yet), so this runner generates
via the demo path: `book_simulator.simulate_book()` at that day offset,
wrapped in the same Fixture*Connector classes `fixtures.py` already uses,
then drafted with the LIVE Anthropic writer (opus-4-8, corpus-wired
org_context per Phase 1/2 of this dispatch) and scored with the live N-run
judge (sonnet-4-6).

Manual invocation only -- no scheduler, no standing job (profile risk
posture; see dispatch Decisions). Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from eval.judge_anthropic import AnthropicQualityJudge, JUDGE_PROMPT_VERSION
from eval.judge_nrun import aggregate
from ultra_csm.agent1 import build_reason_draft_request_for_account
from ultra_csm.agent1.slot_b import AnthropicReasonDraftWriter, SLOT_B_PROMPT_VERSION
from ultra_csm.data_plane.book_simulator import simulate_book
from ultra_csm.data_plane.contracts import CustomerDataPlane
from ultra_csm.data_plane.fixtures import (
    DEFAULT_TENANT,
    FixtureCRMDataConnector,
    FixtureCSPlatformConnector,
    FixtureProductTelemetryConnector,
    account_id_for,
)
from ultra_csm.data_plane.synthetic_book import SEED_DATE, build_synthetic_book

ANCHOR_PATH = Path.home() / "ultra-csm-corpus-runs" / "live-reseed-20260704" / "anchor.json"
ARTIFACT_DIR = Path(__file__).with_name("gold")
SCHEMA_VERSION = 1
DEFAULT_RUNS_PER_CANDIDATE = 3

# Three narrative accounts spanning distinct lifecycle stages (onboarding,
# expanding, renewal -- see synthetic_book.py's _ACCT_DATA arc grouping),
# each confirmed to build a live Slot B request (customer_contact_allowed)
# at the anchor day. Not every account in the book yields a request at a
# given day (evidence-driven, not every slug is None-safe) -- these three
# are the ones verified to.
DEFAULT_SLUGS = ("pinehill-transport", "meridian-fleet", "harborview-fleet")


def load_anchor(anchor_path: Path = ANCHOR_PATH) -> dict[str, Any]:
    return json.loads(anchor_path.read_text(encoding="utf-8"))


def story_day_as_of(anchor: dict[str, Any]) -> tuple[int, str]:
    """Return (anchor_day, fixture_as_of_date) for the frozen anchor.

    `anchor_day` is the day-offset from the narrative SEED_DATE
    (2026-06-21); `fixture_as_of_date` is that offset applied to SEED_DATE
    -- the same date space every Slot B evidence/priority calculation in
    this repo already uses (see data_simulator.py, book_simulator.py).
    """

    day = int(anchor["anchor_day"])
    as_of = (date.fromisoformat(SEED_DATE) + timedelta(days=day)).isoformat()
    return day, as_of


def build_story_day_plane(day: int, *, tenant: str = DEFAULT_TENANT) -> CustomerDataPlane:
    base = build_synthetic_book()
    mutated = simulate_book(base, day_offset=day)
    return CustomerDataPlane(
        crm=FixtureCRMDataConnector(tenant=tenant, data=mutated),
        cs=FixtureCSPlatformConnector(data=mutated),
        telemetry=FixtureProductTelemetryConnector(data=mutated),
    )


def build_judge_live_artifact(
    *,
    anchor_path: Path = ANCHOR_PATH,
    slugs: tuple[str, ...] = DEFAULT_SLUGS,
    runs_per_candidate: int = DEFAULT_RUNS_PER_CANDIDATE,
    writer: AnthropicReasonDraftWriter | None = None,
    judge: AnthropicQualityJudge | None = None,
) -> dict[str, Any]:
    anchor = load_anchor(anchor_path)
    day, as_of = story_day_as_of(anchor)
    plane = build_story_day_plane(day)
    writer = writer or AnthropicReasonDraftWriter()
    judge = judge or AnthropicQualityJudge(reasoning=True)

    candidates = []
    for slug in slugs:
        account_id = account_id_for(slug)
        request = build_reason_draft_request_for_account(
            plane, DEFAULT_TENANT, account_id, as_of=as_of,
        )
        if request is None:
            raise RuntimeError(
                f"no Slot B request built for narrative account {slug!r} at day {day}"
            )
        output = writer.write(request)

        request_dict = asdict(request)
        request_dict["prompt_version"] = SLOT_B_PROMPT_VERSION
        output_dict = asdict(output)
        output_dict["cited_evidence_ids"] = list(output.cited_evidence_ids)

        vectors = [judge.score_output(request_dict, output_dict) for _ in range(runs_per_candidate)]
        agg = aggregate(vectors)

        candidates.append({
            "candidate_id": slug,
            "account_id": account_id,
            "disposition": request.disposition,
            "customer_contact_allowed": request.customer_contact_allowed,
            "has_golden_exemplars": bool(
                (request.org_context or {}).get("golden_exemplars")
            ),
            "request": request_dict,
            "output": output_dict,
            "runs": vectors,
            "agg": agg,
        })

    artifact = {
        "artifact": "judge_live_csm",
        "schema_version": SCHEMA_VERSION,
        "generated_by": "eval.judge_live_csm",
        "anchor_day": day,
        "anchor_fixture_as_of": as_of,
        "anchor_tag": anchor.get("tag"),
        "anchor_source": str(anchor_path),
        "draft_model_id": writer.model_id,
        "judge_model_id": judge.model_id,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_reasoning": judge.reasoning,
        "runs_per_candidate": runs_per_candidate,
        "book_source": (
            "Universe v2 35-account narrative book (synthetic_book.py), "
            "advanced to the anchor's story day via book_simulator.simulate_book(). "
            "No daily operating-artifact snapshot of generated drafts exists yet in "
            "this repo for a given anchor day, so drafts are generated live via this "
            "demo path rather than read from a prior sweep artifact, per this "
            "dispatch's Decisions section."
        ),
        "candidates": candidates,
        "claim_boundary": (
            "judge not human-validated (kappa pending owner labels); this run proves "
            "judge-on-live PLUMBING for one real story day, not draft quality at large"
        ),
    }
    return artifact


def write_judge_live_artifact(
    *,
    anchor_path: Path = ANCHOR_PATH,
    slugs: tuple[str, ...] = DEFAULT_SLUGS,
    runs_per_candidate: int = DEFAULT_RUNS_PER_CANDIDATE,
    output_dir: Path = ARTIFACT_DIR,
) -> tuple[dict[str, Any], Path]:
    artifact = build_judge_live_artifact(
        anchor_path=anchor_path, slugs=slugs, runs_per_candidate=runs_per_candidate,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"judge_live_{artifact['anchor_day']}.json"
    output_path.write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return artifact, output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_CANDIDATE)
    parser.add_argument("--anchor", default=str(ANCHOR_PATH))
    parser.add_argument("--output-dir", default=str(ARTIFACT_DIR))
    args = parser.parse_args(argv)

    artifact, output_path = write_judge_live_artifact(
        anchor_path=Path(args.anchor),
        runs_per_candidate=args.runs,
        output_dir=Path(args.output_dir),
    )
    for candidate in artifact["candidates"]:
        print(
            f"{candidate['candidate_id']:24} disposition={candidate['disposition']:24} "
            f"exemplars={candidate['has_golden_exemplars']} "
            f"pass={candidate['agg']['aggregate_pass']}"
        )
    print(f"artifact -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
