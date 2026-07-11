"""Generate or verify static JSON fixtures for the hosted read-only demo."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

# The seeded database serializes timezone-aware ledger timestamps.  Pin the
# exporter itself to UTC before importing the application so committed fixture
# bytes do not depend on the host running the export (for example, a developer
# laptop in America/New_York versus GitHub's UTC Linux runner).
os.environ["TZ"] = "UTC"
if hasattr(time, "tzset"):
    time.tzset()
os.environ.setdefault("ULTRA_CSM_DEMO_NOAUTH", "1")

from ultra_csm.api import app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui" / "public" / "demo-api"
DAYS = range(134, 141)


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _post(client: TestClient, path: str) -> Any:
    response = client.post(path)
    response.raise_for_status()
    return response.json()


def _proposal_id_map(proposals: dict[str, Any]) -> dict[str, str]:
    """Map runtime proposal UUIDs to IDs derived from stable proposal semantics."""

    replacements: dict[str, str] = {}
    for proposal in proposals["proposals"]:
        runtime_id = proposal["proposal_id"]
        semantic_proposal = {key: value for key, value in proposal.items() if key != "proposal_id"}
        fingerprint = json.dumps(
            semantic_proposal,
            separators=(",", ":"),
            sort_keys=True,
        )
        replacements[runtime_id] = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"ultra-csm:hosted-readonly:day-{DAYS[-1]}:proposal:{fingerprint}",
            )
        )
    return replacements


def _replace_proposal_ids(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_proposal_ids(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_proposal_ids(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def build_fixture_bytes() -> dict[str, bytes]:
    """Build the complete deterministic hosted fixture set without repository writes."""

    payloads: dict[str, Any] = {}
    last_day = DAYS[-1]
    with TestClient(app) as client:
        work_item_counts: dict[str, int] = {}
        for day in DAYS:
            accounts = _get(client, f"/accounts?day={day}")
            sweep = _post(client, f"/sweep?day={day}")
            payloads[f"accounts-day-{day}.json"] = accounts
            payloads[f"sweep-day-{day}.json"] = sweep
            work_item_counts[str(day)] = len(sweep["work_items"])

            account_ids = sorted(
                {
                    item["account_id"]
                    for item in sweep["work_items"]
                    if item.get("account_id") is not None
                }
            )
            for account_id in account_ids:
                payloads[f"account-{account_id}-brief-day-{day}.json"] = _get(
                    client, f"/accounts/{account_id}/brief?day={day}"
                )
                reconciliation = client.get(f"/accounts/{account_id}/reconciliation?day={day}")
                if reconciliation.status_code == 200:
                    payloads[f"account-{account_id}-reconciliation-day-{day}.json"] = (
                        reconciliation.json()
                    )

        # `accounts` / `account_ids` now hold the last day's values; manifest keys
        # below keep their original day-140 semantics for backward compatibility.
        health = _get(client, "/health")
        proposals = _get(client, "/proposals")
        # Seven exported days x ~13 items x ~4 events each: limit=50 would
        # drop the day-140 receipts the queue rail renders.
        ledger = _get(client, "/ledger?limit=500")
        action_control = _get(client, "/demo/action-control/vertical-slice")

        payloads.update(
            {
                "health.json": health,
                "proposals.json": proposals,
                "ledger.json": ledger,
                "action-control-vertical-slice-v1.json": action_control,
                "comms-slack.json": {"pending": [], "auth": "hosted-readonly"},
                "comms-notion.json": {"pending": [], "auth": "hosted-readonly"},
            }
        )

        payloads["manifest.json"] = {
            "mode": "hosted-readonly",
            "day": last_day,
            "days": list(DAYS),
            "account_count": accounts["account_count"],
            "work_item_count": work_item_counts[str(last_day)],
            "work_item_counts": work_item_counts,
            "proposal_count": len(proposals["proposals"]),
            "action_control_contract_version": action_control["schema_version"],
            "exported_account_detail_count": len(account_ids),
            "write_routes_exported": False,
        }

    replacements = _proposal_id_map(proposals)
    return {
        name: _json_bytes(_replace_proposal_ids(payload, replacements))
        for name, payload in payloads.items()
    }


def write_fixtures(fixtures: dict[str, bytes], output_dir: Path = OUT) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*.json"):
        if path.name not in fixtures:
            path.unlink()
    for name, content in fixtures.items():
        (output_dir / name).write_bytes(content)


def check_fixtures(fixtures: dict[str, bytes], output_dir: Path = OUT) -> list[str]:
    committed_names = {path.name for path in output_dir.glob("*.json")}
    generated_names = set(fixtures)
    drift = [f"missing committed fixture: {name}" for name in generated_names - committed_names]
    drift.extend(
        f"unexpected committed fixture: {name}" for name in committed_names - generated_names
    )
    drift.extend(
        f"fixture bytes differ: {name}"
        for name in generated_names & committed_names
        if (output_dir / name).read_bytes() != fixtures[name]
    )
    return sorted(drift)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare a fresh in-memory export to committed fixtures without writing",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT,
        help="fixture destination for generation (defaults to the committed directory)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    fixtures = build_fixture_bytes()
    if args.check:
        drift = check_fixtures(fixtures, args.output_dir)
        if drift:
            for message in drift:
                print(message)
            print("hosted read-only fixtures are stale; run make hosted-readonly-demo-generate")
            return 1
        print("hosted read-only fixture bytes are current")
        return 0

    write_fixtures(fixtures, args.output_dir)
    try:
        destination = args.output_dir.relative_to(ROOT)
    except ValueError:
        destination = args.output_dir
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
