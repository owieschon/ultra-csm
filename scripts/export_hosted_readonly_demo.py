"""Export static JSON fixtures for the hosted read-only Vercel demo."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

os.environ.setdefault("ULTRA_CSM_DEMO_NOAUTH", "1")

from ultra_csm.api import app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui" / "public" / "demo-api"
DAY = 140


def _write(name: str, payload: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _post(client: TestClient, path: str) -> Any:
    response = client.post(path)
    response.raise_for_status()
    return response.json()


def main() -> int:
    with TestClient(app) as client:
        health = _get(client, "/health")
        accounts = _get(client, f"/accounts?day={DAY}")
        sweep = _post(client, f"/sweep?day={DAY}")
        proposals = _get(client, "/proposals")
        ledger = _get(client, "/ledger?limit=50")
        action_control = _get(client, "/demo/action-control/vertical-slice")

        _write("health.json", health)
        _write(f"accounts-day-{DAY}.json", accounts)
        _write(f"sweep-day-{DAY}.json", sweep)
        _write("proposals.json", proposals)
        _write("ledger.json", ledger)
        _write("action-control-vertical-slice-v1.json", action_control)
        _write("comms-slack.json", {"pending": [], "auth": "hosted-readonly"})
        _write("comms-notion.json", {"pending": [], "auth": "hosted-readonly"})

        account_ids = sorted(
            {
                item["account_id"]
                for item in sweep["work_items"]
                if item.get("account_id") is not None
            }
        )
        for account_id in account_ids:
            _write(
                f"account-{account_id}-brief-day-{DAY}.json",
                _get(client, f"/accounts/{account_id}/brief?day={DAY}"),
            )
            reconciliation = client.get(
                f"/accounts/{account_id}/reconciliation?day={DAY}"
            )
            if reconciliation.status_code == 200:
                _write(
                    f"account-{account_id}-reconciliation-day-{DAY}.json",
                    reconciliation.json(),
                )

        _write(
            "manifest.json",
            {
                "mode": "hosted-readonly",
                "day": DAY,
                "account_count": accounts["account_count"],
                "work_item_count": len(sweep["work_items"]),
                "proposal_count": len(proposals["proposals"]),
                "action_control_contract_version": action_control["schema_version"],
                "exported_account_detail_count": len(account_ids),
                "write_routes_exported": False,
            },
        )

    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
