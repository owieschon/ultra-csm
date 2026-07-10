"""Generate or verify the frozen Action Control vertical-slice artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg

from ultra_csm.action_control_demo import run_action_control_synthetic_scenario
from ultra_csm.action_control_contract import (
    action_control_json_schema,
)
from ultra_csm.platform import boot_seeded_cluster


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "contracts" / "action-control.vertical-slice.v1.schema.json"
EXAMPLE_PATH = ROOT / "ui" / "public" / "demo-api" / "action-control-vertical-slice-v1.json"
MIGRATIONS = ROOT / "migrations"


def _render(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _sync(path: Path, expected: str, *, check: bool) -> bool:
    if check:
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual != expected:
            print(f"stale: {path.relative_to(ROOT)}")
            return False
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(expected, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    schema = _render(action_control_json_schema())
    with boot_seeded_cluster(MIGRATIONS) as (cluster, _dsn):
        with psycopg.connect(**cluster.dsn(user="app_runtime")) as conn:
            example = _render(
                run_action_control_synthetic_scenario(conn).model_dump(mode="json")
            )
    results = (
        _sync(SCHEMA_PATH, schema, check=args.check),
        _sync(EXAMPLE_PATH, example, check=args.check),
    )
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
