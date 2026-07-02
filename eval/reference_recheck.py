"""Build a blinded re-check deck for owner-approved reference scores.

The re-check deck is generated after the owner fills `reference_review_iteration3`.
It samples across dimensions and owner buckets, then strips the prior score, bucket,
judge score, and judge rationale from the labeler-facing file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from eval.reference_review import REFERENCE_REVIEW_PATH

RECHECK_PATH = Path(__file__).resolve().parent / "gold" / "reference_recheck_iteration3.json"
RECHECK_KEY_PATH = (
    Path(__file__).resolve().parent / "gold" / "reference_recheck_iteration3_key.json"
)
DEFAULT_SAMPLE_SIZE = 40


def _load_review(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _approved_cards(review: dict) -> list[dict]:
    cards = []
    for card in review.get("cards", ()):
        score = card.get("owner_review", {}).get("final_reference_score")
        if score not in (1, 2, 3):
            raise ValueError(
                f"{card.get('candidate_id')}:{card.get('dimension')} is missing final_reference_score"
            )
        cards.append(card)
    return cards


def _target_counts(counts: Counter[str], sample_size: int) -> dict[str, int]:
    total = sum(counts.values())
    raw = {
        key: (value * sample_size / total)
        for key, value in counts.items()
    }
    targets = {key: int(value) for key, value in raw.items()}
    remainder = sample_size - sum(targets.values())
    ranked = sorted(raw, key=lambda key: (raw[key] - targets[key], counts[key], key), reverse=True)
    for key in ranked[:remainder]:
        targets[key] += 1
    return dict(sorted(targets.items()))


def _card_sort_key(card: dict) -> str:
    raw = f"{card['candidate_id']}:{card['dimension']}:{card['owner_review']['bucket']}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _select_cards(cards: list[dict], sample_size: int) -> tuple[list[dict], dict[str, int], dict[str, int]]:
    dimension_targets = _target_counts(Counter(card["dimension"] for card in cards), sample_size)
    bucket_targets = _target_counts(
        Counter(str(card["owner_review"]["bucket"]) for card in cards),
        sample_size,
    )
    selected: list[dict] = []
    selected_ids: set[tuple[str, str]] = set()
    dimension_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()

    groups: dict[tuple[str, str], list[dict]] = {}
    for card in sorted(cards, key=_card_sort_key):
        groups.setdefault((card["dimension"], str(card["owner_review"]["bucket"])), []).append(card)

    # First pass: one from every populated dimension/bucket cell, so hard buckets
    # cannot disappear from the sample.
    for key in sorted(groups):
        card = groups[key][0]
        selected.append(card)
        selected_ids.add((card["candidate_id"], card["dimension"]))
        dimension_counts[card["dimension"]] += 1
        bucket_counts[str(card["owner_review"]["bucket"])] += 1

    for card in sorted(cards, key=_card_sort_key):
        if len(selected) >= sample_size:
            break
        identity = (card["candidate_id"], card["dimension"])
        if identity in selected_ids:
            continue
        dimension = card["dimension"]
        bucket = str(card["owner_review"]["bucket"])
        if dimension_counts[dimension] >= dimension_targets[dimension]:
            continue
        if bucket_counts[bucket] >= bucket_targets[bucket]:
            continue
        selected.append(card)
        selected_ids.add(identity)
        dimension_counts[dimension] += 1
        bucket_counts[bucket] += 1

    for card in sorted(cards, key=_card_sort_key):
        if len(selected) >= sample_size:
            break
        identity = (card["candidate_id"], card["dimension"])
        if identity in selected_ids:
            continue
        selected.append(card)
        selected_ids.add(identity)

    selected = sorted(selected, key=_card_sort_key)[:sample_size]
    return selected, dimension_targets, bucket_targets


def _recheck_id(card: dict) -> str:
    digest = hashlib.sha256(
        f"{card['candidate_id']}:{card['dimension']}:iteration3".encode("utf-8")
    ).hexdigest()[:16]
    return f"reference-recheck-{digest}"


def build_reference_recheck(review: dict, *, sample_size: int = DEFAULT_SAMPLE_SIZE) -> tuple[dict, dict]:
    cards = _approved_cards(review)
    selected, dimension_targets, bucket_targets = _select_cards(cards, sample_size)
    deck_cards = []
    key_records = []
    for card in selected:
        recheck_id = _recheck_id(card)
        deck_cards.append(
            {
                "recheck_id": recheck_id,
                "candidate_id": card["candidate_id"],
                "layer": card["layer"],
                "dimension": card["dimension"],
                "request": card["request"],
                "output": card["output"],
                "recheck_score": None,
                "notes": "",
            }
        )
        key_records.append(
            {
                "recheck_id": recheck_id,
                "candidate_id": card["candidate_id"],
                "layer": card["layer"],
                "dimension": card["dimension"],
                "prior_final_reference_score": card["owner_review"]["final_reference_score"],
                "owner_bucket": card["owner_review"]["bucket"],
            }
        )

    dimension_counts = Counter(card["dimension"] for card in selected)
    bucket_counts = Counter(str(card["owner_review"]["bucket"]) for card in selected)
    deck = {
        "artifact": "slot_b_iteration3_reference_recheck",
        "sample_size": len(deck_cards),
        "blind": True,
        "dimension_targets": dimension_targets,
        "dimension_counts": dict(sorted(dimension_counts.items())),
        "bucket_stratified": True,
        "gate": {
            "max_disagreements": 2,
            "action_if_failed": "tighten affected anchor and re-pass before applying references",
        },
        "claim_boundary": {
            "prior_scores_hidden": True,
            "strata_hidden": True,
            "model_outputs_hidden": True,
        },
        "cards": deck_cards,
    }
    key = {
        "artifact": "slot_b_iteration3_reference_recheck_key",
        "sample_size": len(key_records),
        "bucket_targets": bucket_targets,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "key_records": key_records,
    }
    return deck, key


def _assert_blind(deck: dict) -> None:
    raw = json.dumps(deck, sort_keys=True)
    forbidden = (
        "prior_final_reference_score",
        "owner_bucket",
        "judge_score",
        "judge_reason",
        "reference_stale",
        "judge_error",
        "definition_ambiguity",
    )
    leaks = [token for token in forbidden if token in raw]
    if leaks:
        raise ValueError(f"recheck deck leaks hidden fields: {', '.join(leaks)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", default=str(REFERENCE_REVIEW_PATH))
    parser.add_argument("--output", default=str(RECHECK_PATH))
    parser.add_argument("--key-output", default=str(RECHECK_KEY_PATH))
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    args = parser.parse_args(argv)

    deck, key = build_reference_recheck(_load_review(Path(args.review)), sample_size=args.sample_size)
    _assert_blind(deck)
    output = Path(args.output)
    key_output = Path(args.key_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(deck, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    key_output.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "reference recheck: "
        f"{deck['sample_size']} cards "
        f"dimensions={deck['dimension_counts']} bucket_stratified=true -> {output}"
    )
    print(f"held-out key -> {key_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
